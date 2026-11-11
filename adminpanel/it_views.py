import io
from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import FileResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_POST

from users.roles import can_operate_system
from django.contrib.auth import get_user_model
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from .backup_service import BackupError, backup_directory, create_backup, get_backup, list_backups, next_backup_run, restore_backup, import_backup_archive, archive_payload, _audit
from .models import BackupSchedule, PageVisitLog, SecurityEvent


class BackupScheduleForm(forms.ModelForm):
    weekday = forms.TypedChoiceField(coerce=int, choices=list(enumerate(['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'])))

    class Meta:
        model = BackupSchedule
        fields = ['enabled', 'frequency', 'run_at', 'weekday', 'recipients']
        widgets = {'run_at': forms.TimeInput(format='%H:%M', attrs={'type': 'time'})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['recipients'].queryset = get_user_model().objects.filter(is_active=True).exclude(email='').order_by('username')
        self.fields['recipients'].label = 'Backup email recipients'
        self.fields['recipients'].label_from_instance = lambda user: f'{user.username} ({user.email})'
        self.fields['recipients'].help_text = 'Select the active users whose mailboxes should receive the database recovery archive.'
        for field in self.fields.values():
            field.widget.attrs['class'] = 'form-check-input' if isinstance(field.widget, forms.CheckboxInput) else 'form-control'

    def clean(self):
        cleaned = super().clean()
        recipients = cleaned.get('recipients')
        if cleaned.get('enabled') and not recipients:
            self.add_error('recipients', 'Choose at least one backup email recipient.')
        for user in recipients or []:
            try:
                validate_email(user.email)
            except ValidationError:
                self.add_error('recipients', f'{user.username} needs a valid email address first.')
        return cleaned

    def clean_enabled(self):
        enabled = self.cleaned_data['enabled']
        if enabled and not settings.DB_BACKUP_ENABLED:
            raise forms.ValidationError('Backups are disabled in this environment.')
        return enabled


@login_required
def it_dashboard(request):
    if not can_operate_system(request.user):
        return HttpResponseForbidden('Only IT and administrators can access operations.')
    return render(request, 'adminpanel/it_dashboard.html', {
        'open_security_count': SecurityEvent.objects.filter(is_suspicious=True, status='open').count(),
        'recent_security': SecurityEvent.objects.filter(is_suspicious=True).select_related('user').order_by('-occurred_at')[:8],
        'today_visits': PageVisitLog.objects.filter(visited_at__date=timezone.localdate()).count(),
        'recent_visits': PageVisitLog.objects.select_related('user').order_by('-visited_at')[:8],
    })


def _recovery_context(request):
    snapshots = []
    try:
        snapshots = list_backups()
    except (BackupError, OSError):
        messages.warning(request, 'Backup storage is unavailable. Check the private backup directory configuration.')
    return {
        'snapshots': snapshots,
        'backups_enabled': settings.DB_BACKUP_ENABLED,
        'restore_enabled': settings.DB_BACKUP_ENABLED and settings.DB_RESTORE_ENABLED and settings.DB_MAINTENANCE_MODE,
        'local_email_test': settings.DB_BACKUP_ALLOW_TEST_EMAIL,
        'restorable_snapshots': [row for row in snapshots if row['available_locally']],
        'operations_timezone': timezone.get_current_timezone_name(),
    }


@login_required
def it_backups(request):
    if not can_operate_system(request.user):
        return HttpResponseForbidden('Only IT and administrators can access backups.')
    schedule, _ = BackupSchedule.objects.get_or_create(key='database')
    form = BackupScheduleForm(request.POST or None, instance=schedule)
    if request.method == 'POST' and form.is_valid():
        schedule = form.save(commit=False)
        schedule.updated_by = request.user
        schedule.next_run = next_backup_run(schedule.frequency, schedule.run_at, schedule.weekday) if schedule.enabled else None
        schedule.save()
        form.save_m2m()
        _audit('schedule_updated', request.user.username, enabled=schedule.enabled, frequency=schedule.frequency)
        messages.success(request, 'Backup schedule saved. The operations worker must be running to execute it.')
        return redirect('it_backups')
    worker_active = bool(schedule.worker_heartbeat and 0 <= (timezone.now() - schedule.worker_heartbeat).total_seconds() < 90)
    return render(request, 'adminpanel/it_backups.html', {
        **_recovery_context(request),
        'schedule_form': form, 'schedule': schedule, 'worker_active': worker_active,
    })


@login_required
def it_recovery(request):
    if not can_operate_system(request.user):
        return HttpResponseForbidden('Only IT and administrators can access database recovery.')
    return render(request, 'adminpanel/it_recovery.html', _recovery_context(request))


@transaction.non_atomic_requests
@login_required
@require_POST
def it_backup_now(request):
    if not can_operate_system(request.user):
        return HttpResponseForbidden('Only IT and administrators can run backups.')
    try:
        record = create_backup(request.user.username)
        messages.success(request, f"Backup archive emailed: {record['id']} ({record['email_status']}).")
    except BackupError as exc:
        messages.error(request, str(exc))
    except OSError:
        messages.error(request, 'Backup could not complete. Check configuration, storage and database tooling; another operation may be running.')
    return redirect('it_backups')


@login_required
def it_backup_download(request, backup_id):
    if not can_operate_system(request.user):
        return HttpResponseForbidden('Only IT and administrators can download backups.')
    try:
        record, path = get_backup(backup_id, verify=True)
    except BackupError:
        from django.http import Http404
        raise Http404('Backup unavailable')
    _audit('backup_downloaded', request.user.username, backup=backup_id)
    return FileResponse(io.BytesIO(archive_payload(record, path)), as_attachment=True, filename='database-backup-' + record['id'] + '.zip')


@transaction.non_atomic_requests
@login_required
@require_POST
def it_restore(request):
    if not can_operate_system(request.user):
        return HttpResponseForbidden('Only IT and administrators can restore databases.')
    if not request.user.check_password(request.POST.get('password', '')):
        _audit('restore_password_denied', request.user.username)
        messages.error(request, 'Password confirmation failed. Nothing was restored.')
        return redirect('it_recovery')
    try:
        restore_backup(request.POST.get('backup_id', ''), request.user.username, request.POST.get('confirmation', ''))
    except (BackupError, OSError) as exc:
        messages.error(request, str(exc) if isinstance(exc, BackupError) else 'Restore failed. Check the private operations audit and server configuration.')
        return redirect('it_recovery')
    logout(request)
    messages.success(request, 'Database restored. Sign in again to verify the restored system.')
    return redirect('login')


@login_required
@require_POST
def it_backup_import(request):
    if not can_operate_system(request.user):
        return HttpResponseForbidden('Only IT and administrators can import recovery archives.')
    upload = request.FILES.get('archive')
    if not upload:
        messages.error(request, 'Select the ZIP recovery archive from your backup email.')
        return redirect('it_recovery')
    try:
        record = import_backup_archive(upload, request.user.username)
        messages.success(request, 'Recovery archive verified. Select snapshot ' + record['id'] + ' and confirm the restore.')
    except BackupError as exc:
        messages.error(request, str(exc))
    return redirect('it_recovery')
