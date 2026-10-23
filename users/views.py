from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.views import PasswordResetView
import logging
from .forms import CustomUserCreationForm, CustomLoginForm, StrictPasswordResetForm
from .models import CustomUser
from projects.models import StudentProfile
from django.conf import settings
from django.http import HttpResponseForbidden
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from adminpanel.models import Notification, SecurityEvent
from adminpanel.security_service import device_label, masked_ip, record_failed_login, record_login

logger = logging.getLogger(__name__)


def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            role = request.POST.get('role')

            # Prevent public self-registration into privileged roles
            if role in ['admin', 'dean', 'centrehead', 'financialadmin']:
                form.add_error(None, "You are not allowed to register with this role.")
                return render(request, 'users/register.html', {'form': form})

            user = form.save(commit=False)
            user.role = role
            user.save()

            # Automatically create StudentProfile if role is student
            if role == 'student':
                supervisor = CustomUser.objects.filter(role='admin').first()
                StudentProfile.objects.create(user=user, supervisor=supervisor)

            return redirect('login')
    else:
        form = CustomUserCreationForm()
    return render(request, 'users/register.html', {'form': form})



def login_view(request):
    requested_next = request.POST.get('next') or request.GET.get('next')
    if requested_next and url_has_allowed_host_and_scheme(
        requested_next,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        request.session['post_login_redirect'] = requested_next

    form = CustomLoginForm(data=request.POST or None)
    if form.is_valid():
        user = form.get_user()
        login(request, user)
        security_event = record_login(request, user)
        if security_event.is_suspicious:
            return redirect('security_event_review', event_id=security_event.id)

        safe_destination = request.session.pop('post_login_redirect', None)
        if safe_destination:
            return redirect(safe_destination)

        # Redirect based on user role
        return redirect(_role_home_name(user))
    if request.method == 'POST':
        record_failed_login(request, request.POST.get('username', '').strip())
    return render(request, 'users/login.html', {'form': form})


def _role_home_name(user):
    if user.role in {'admin', 'dean', 'centrehead'}:
        return 'overview'
    if user.role == 'supervisor':
        return 'supervisor_dashboard_portal'
    if user.role == 'manager':
        return 'manager_dashboard'
    if user.role == 'financialadmin':
        return 'finance'
    if user.role == 'student':
        return 'student_dashboard'
    return 'dashboard'


@login_required
def security_center(request):
    events = request.user.security_events.filter(is_suspicious=True).order_by('-occurred_at')[:50]
    return render(request, 'users/security_center.html', {'security_events': events})


@login_required
def security_event_review(request, event_id):
    event = SecurityEvent.objects.filter(pk=event_id, user=request.user, is_suspicious=True).first()
    if not event:
        return HttpResponseForbidden('This security event does not belong to your account.')

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'confirm':
            event.status = 'confirmed'
            event.reviewed_at = timezone.now()
            event.save(update_fields=['status', 'reviewed_at'])
            request.session.pop('pending_security_event_id', None)
            messages.success(request, 'Thank you. This activity is now confirmed as yours.')
            safe_destination = request.session.pop('post_login_redirect', None)
            if safe_destination and url_has_allowed_host_and_scheme(
                safe_destination,
                allowed_hosts={request.get_host()},
                require_https=request.is_secure(),
            ):
                return redirect(safe_destination)
            return redirect('security_center')
        if action == 'secure':
            request.session['security_password_event_id'] = event.id
            return redirect('security_password_change')

    return render(request, 'users/security_event_review.html', {
        'security_event': event,
        'security_local_time': timezone.localtime(event.occurred_at),
        'security_ip': masked_ip(event.ip_address),
        'security_device': device_label(event.user_agent),
    })


@login_required
def security_password_change(request):
    event_id = request.session.get('security_password_event_id')
    event = SecurityEvent.objects.filter(pk=event_id, user=request.user, is_suspicious=True).first()
    if not event:
        messages.info(request, 'Choose a security alert before starting the protected password-change flow.')
        return redirect('security_center')

    form = PasswordChangeForm(request.user, request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        update_session_auth_hash(request, user)
        event.status = 'secured'
        event.reviewed_at = timezone.now()
        event.save(update_fields=['status', 'reviewed_at'])
        request.session.pop('security_password_event_id', None)
        request.session.pop('pending_security_event_id', None)
        notification = Notification.objects.create(
            title='Your account password was changed',
            body='Your password was changed through the Account Security workflow. Other signed-in sessions must authenticate again.',
            priority='high',
            audience='specific',
        )
        notification.recipients.add(request.user)
        messages.success(request, 'Password changed. Other signed-in sessions have been invalidated.')
        return redirect('security_center')
    return render(request, 'users/security_password_change.html', {
        'form': form,
        'security_event': event,
    })


def logout_view(request):
    logout(request)
    return redirect('login')


class DebugPasswordResetView(PasswordResetView):
    template_name = 'users/password_reset.html'
    email_template_name = 'users/password_reset_email.html'
    subject_template_name = 'users/password_reset_subject.txt'
    form_class = StrictPasswordResetForm

    def form_valid(self, form):
        email = form.cleaned_data.get('email', '').strip()
        matching_users = list(form.get_users(email))
        self.from_email = getattr(settings, 'EMAIL_HOST_USER', '') or getattr(settings, 'DEFAULT_FROM_EMAIL', None)
        logger.info("Password reset requested for %s. Matching active users: %s", email, len(matching_users))
        logger.info("Password reset sender resolved to %s", self.from_email)
        if not matching_users:
            logger.warning("Password reset blocked. No active user found for email %s", email)
            form.add_error('email', 'We could not find an active account with that email address.')
            return self.form_invalid(form)

        if not self.from_email:
            logger.error("Password reset blocked. No SMTP sender address is configured.")
            form.add_error(None, 'Password reset email is not configured correctly on the server.')
            return self.form_invalid(form)

        try:
            response = super().form_valid(form)
            logger.info("Password reset email sent successfully for %s", email)
            return response
        except Exception as exc:
            logger.exception("Password reset email failed for %s", email)
            form.add_error(None, f"We could not send the reset email. Reason: {exc}")
            return self.form_invalid(form)
