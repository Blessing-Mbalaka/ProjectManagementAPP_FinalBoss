from django import forms
from .models import SupervisorFeedback, Notification
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

