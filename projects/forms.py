# projects/forms.py
from django import forms
from .models import DailyTask, StudentProfile, Submission, FeedbackReply, Meeting, ChatMessage, Project, Assignment, TeamMember, Task, WeeklyReport
from django.contrib.auth import get_user_model 

# forms.py
class DailyTaskForm(forms.ModelForm):
    def __init__(self, *args, user=None, work_date=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.work_date = work_date
        if user is None:
            self.fields['task'].queryset = Task.objects.none()
            return

        from projects.work_scope import workable_tasks_for

        existing_ids = DailyTask.objects.filter(
            user=user,
            work_date=work_date,
            task__isnull=False,
        ).values_list('task_id', flat=True)
        self.fields['task'].queryset = workable_tasks_for(user).exclude(id__in=existing_ids).order_by(
            'project__name', 'title'
        )

    class Meta:
        model = DailyTask
        fields = ['task', 'work_date']
        widgets = {
            'task': forms.Select(attrs={'class': 'form-select'}),
            'work_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }


class WeeklyReportForm(forms.ModelForm):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        from projects.work_scope import assigned_projects_for, manageable_projects_for

        if user is None:
            self.fields['project'].queryset = Project.objects.none()
        else:
            manageable = manageable_projects_for(user)
            assigned = assigned_projects_for(user)
            self.fields['project'].queryset = (manageable | assigned).distinct().order_by('name')

    def clean_week_start(self):
        value = self.cleaned_data['week_start']
        if value.weekday() != 0:
            raise forms.ValidationError('Choose the Monday that starts the reporting week.')
        return value

    class Meta:
        model = WeeklyReport
        fields = ['project', 'week_start', 'summary', 'attachment']
        widgets = {
            'project': forms.Select(attrs={'class': 'form-select'}),
            'week_start': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'summary': forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
            'attachment': forms.FileInput(attrs={'class': 'form-control'}),
        }


class StudentProfileForm(forms.ModelForm):
    class Meta:
        model = StudentProfile
        fields = ['program', 'co_supervisor', 'research_title', 'year']
        widgets = {
            'program': forms.Select(attrs={'class': 'form-select'}),
            'co_supervisor': forms.TextInput(attrs={'class': 'form-control'}),
            'research_title': forms.TextInput(attrs={'class': 'form-control'}),
            'year': forms.TextInput(attrs={'class': 'form-control'}),
        }

class SubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ['document_type', 'title', 'file', 'notes']
        widgets = {
            'document_type': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'file': forms.FileInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

class FeedbackReplyForm(forms.ModelForm):
    class Meta:
        model = FeedbackReply
        fields = ['message']
        widgets = {
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Write a reply...'}),
        }

class MeetingForm(forms.ModelForm):
    class Meta:
        model = Meeting
        fields = ['date', 'time', 'duration', 'purpose', 'mode']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'duration': forms.NumberInput(attrs={'class': 'form-control'}),
            'purpose': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'mode': forms.Select(attrs={'class': 'form-select'}),
        }

class ChatForm(forms.ModelForm):
    class Meta:
        model = ChatMessage
        fields = ['message', 'attachment']
        widgets = {
            'message': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Type your message...'}),
            'attachment': forms.FileInput(attrs={'class': 'form-control', 'accept': '*/*'})
        }


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'description', 'project_type', 'due_date', 'status']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
        }

class AssignmentForm(forms.ModelForm):
    team_member = forms.ModelChoiceField(
        queryset=TeamMember.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        empty_label="Select team member",
        label="Team member"
    )

    class Meta:
        model = Assignment
        fields = ['team_member', 'responsibility']
        widgets = {
            'responsibility': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        project = kwargs.pop('project', None)
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Only show TeamMembers not already assigned to this project
        qs = TeamMember.objects.select_related('user').exclude(user__role='student')
        if user and getattr(user, 'role', None) not in {'admin', 'dean'}:
            centre_id = getattr(user, 'research_centre_id', None)
            qs = qs.filter(user__research_centre_id=centre_id) if centre_id else qs.none()

        if project:
            assigned_ids = Assignment.objects.filter(project=project)\
                .values_list('team_member_id', flat=True)
            qs = qs.exclude(id__in=assigned_ids)

        self.fields['team_member'].queryset = qs.order_by('full_name')

    # (Optional) nicer label in the dropdown
    def label_from_instance(self, obj: TeamMember):
        if obj.user and (obj.user.get_full_name() or obj.user.username):
            base = obj.user.get_full_name() or obj.user.username
        else:
            base = obj.full_name or "Unnamed"
        return f"{base}"


class FileUploadForm(forms.Form):
    file = forms.FileField()


class TaskForm(forms.ModelForm):
    class Meta:
        model = Task
        fields = ['title', 'priority', 'due_date', 'status', 'task_type', 'assigned_to', 'parent_task']

    def __init__(self, *args, **kwargs):
        self.project = kwargs.pop('project', None)  # keep reference
        super().__init__(*args, **kwargs)

        if self.project:
            # Limit parent_task to this project
            self.fields['parent_task'].queryset = Task.objects.filter(project=self.project)

            # Limit assignees to project team users
            team_user_ids = Assignment.objects.filter(project=self.project)\
                .values_list('team_member__user_id', flat=True)
            self.fields['assigned_to'].queryset = get_user_model().objects.filter(id__in=team_user_ids)
        else:
            # If no project passed, make safe defaults
            self.fields['parent_task'].queryset = Task.objects.none()
            self.fields['assigned_to'].queryset = get_user_model().objects.none()

    def clean_assigned_to(self):
        assigned_to = self.cleaned_data.get('assigned_to')
        if assigned_to and self.project:
            team_user_ids = Assignment.objects.filter(project=self.project)\
                .values_list('team_member__user_id', flat=True)
            if assigned_to.id not in team_user_ids:
                raise forms.ValidationError("Selected user is not a member of this project.")
        return assigned_to
