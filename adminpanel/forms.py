from django import forms
from .models import EngagementLog, FinancialProject, SupervisorFeedback, Notification
from projects.models import Project
from django.conf import settings
from django.utils import timezone

class SupervisorFeedbackForm(forms.ModelForm):
    class Meta:
        model = SupervisorFeedback
        fields = ['comments', 'uploaded_file', 'status']
        widgets = {
            'comments': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'uploaded_file': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }


class NotificationForm(forms.ModelForm):
    # Use HTML5 datetime-local
    scheduled_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'})
    )
    expires_at = forms.DateTimeField(
        required=False,
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'})
    )

    class Meta:
        model = Notification
        fields = [
            'title', 'body', 'priority',
            'audience', 'audience_role', 'recipients',
            'is_pinned', 'send_email',
            'scheduled_at', 'expires_at'
        ]
        widgets = {
            'body': forms.Textarea(attrs={'rows': 4}),
            'recipients': forms.SelectMultiple(attrs={'class': 'form-select'}),
            'priority': forms.Select(attrs={'class': 'form-select'}),
            'audience': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean(self):
        cleaned = super().clean()
        audience = cleaned.get('audience')
        audience_role = cleaned.get('audience_role')
        recipients = cleaned.get('recipients')

        if audience == 'role' and not audience_role:
            self.add_error('audience_role', "Please choose a role for the audience.")
        if audience == 'specific' and (not recipients or len(recipients) == 0):
            self.add_error('recipients', "Please select at least one recipient.")
        return cleaned


class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'description', 'project_type', 'status', 'due_date']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter project name',
                'required': True
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Project description (optional)'
            }),
            'project_type': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'due_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
        }

    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            name = name.strip()
            # Check for duplicate (case-insensitive)
            existing = Project.objects.filter(name__iexact=name).exclude(pk=self.instance.pk if self.instance.pk else None)
            if existing.exists():
                raise forms.ValidationError(f"A project named '{name}' already exists. Please use a different name.")
        return name

    def clean(self):
        cleaned = super().clean()
        name = cleaned.get('name')
        if not name or not name.strip():
            raise forms.ValidationError("Project name is required.")
        return cleaned


class FinancialProjectForm(forms.ModelForm):
    project_name = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Bid or opportunity title'}),
    )
    initial_engagement_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
    )
    initial_contact_method = forms.ChoiceField(
        required=False,
        choices=EngagementLog.CONTACT_METHOD_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    initial_engagement_minutes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'What was discussed and agreed?'}),
    )

    class Meta:
        model = FinancialProject
        fields = [
            'client_name', 'company_name', 'company_registration_number', 'industry',
            'company_website', 'company_email', 'company_phone', 'company_address',
            'contact_name', 'contact_role', 'contact_email', 'contact_phone',
            'estimated_value', 'bid_reference', 'bid_deadline', 'applied_date',
            'next_follow_up_date', 'summary',
        ]
        widgets = {
            'client_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Trading or familiar company name'}),
            'company_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Registered company name (optional)'}),
            'company_registration_number': forms.TextInput(attrs={'class': 'form-control'}),
            'industry': forms.TextInput(attrs={'class': 'form-control'}),
            'company_website': forms.URLInput(attrs={'class': 'form-control', 'placeholder': 'https://'}),
            'company_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'company_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'company_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'contact_name': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_role': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Role or position'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'estimated_value': forms.NumberInput(attrs={'class': 'form-control', 'min': '0', 'step': '0.01'}),
            'bid_reference': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Tender/RFQ reference'}),
            'bid_deadline': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'applied_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'next_follow_up_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'summary': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Scope, client need, and next action'}),
        }

    def clean_project_name(self):
        project_name = self.cleaned_data['project_name'].strip()
        if Project.objects.filter(name__iexact=project_name).exists():
            raise forms.ValidationError('A project with this name already exists.')
        return project_name

    def clean_estimated_value(self):
        value = self.cleaned_data.get('estimated_value')
        if value is not None and value < 0:
            raise forms.ValidationError('Estimated value cannot be negative.')
        return value

    def clean(self):
        cleaned = super().clean()
        if not (cleaned.get('contact_email') or '').strip() and not (cleaned.get('contact_phone') or '').strip():
            message = 'Add at least one contact method: email address or phone number.'
            self.add_error('contact_email', message)
            self.add_error('contact_phone', message)
        return cleaned
