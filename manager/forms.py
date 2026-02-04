from django import forms
from .models import Book, Paper, Conference
from projects.models import Project
from users.models import CustomUser

class BookForm(forms.ModelForm):
    class Meta:
        model = Book
        fields = ['title', 'description', 'status', 'due_date', 'lead_author', 'publisher', 'total_chapters', 'completed_chapters']

class PaperForm(forms.ModelForm):
    """Form for Paper model with support for both legacy text and new user reference fields"""
    lead_author_user = forms.ModelChoiceField(
        queryset=CustomUser.objects.all().order_by('first_name', 'last_name'),
        required=False,
        label='Lead Author (User)',
        help_text='Select the lead author from system users'
    )
    co_authors_users = forms.ModelMultipleChoiceField(
        queryset=CustomUser.objects.all().order_by('first_name', 'last_name'),
        required=False,
        label='Co-Authors (Users)',
        help_text='Select co-authors from system users',
        widget=forms.CheckboxSelectMultiple
    )
    assigned_reviewers = forms.ModelMultipleChoiceField(
        queryset=CustomUser.objects.all().order_by('first_name', 'last_name'),
        required=False,
        label='Assigned Reviewers',
        help_text='Select users to review this paper',
        widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = Paper
        fields = [
            'paper_type', 'internal_external', 'title', 'lead_author', 'co_authors',
            'lead_author_user', 'co_authors_users', 'assigned_reviewers',
            'status', 'version', 'abstract', 'manuscript',
            'target_journal', 'submission_date', 'decision_date', 'feedback_text'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'lead_author': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Legacy field - use Lead Author (User) above'}),
            'co_authors': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Legacy field - use Co-Authors (Users) above'}),
            'abstract': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'feedback_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'target_journal': forms.TextInput(attrs={'class': 'form-control'}),
        }

class ConferenceForm(forms.ModelForm):
    """Form for Conference model with support for both legacy text and new user reference fields"""
    lead_author_user = forms.ModelChoiceField(
        queryset=CustomUser.objects.all().order_by('first_name', 'last_name'),
        required=False,
        label='Lead Author (User)',
        help_text='Select the lead author from system users'
    )
    co_authors_users = forms.ModelMultipleChoiceField(
        queryset=CustomUser.objects.all().order_by('first_name', 'last_name'),
        required=False,
        label='Co-Authors (Users)',
        help_text='Select co-authors from system users',
        widget=forms.CheckboxSelectMultiple
    )
    assigned_reviewers = forms.ModelMultipleChoiceField(
        queryset=CustomUser.objects.all().order_by('first_name', 'last_name'),
        required=False,
        label='Assigned Reviewers',
        help_text='Select users to review this paper',
        widget=forms.CheckboxSelectMultiple
    )

    class Meta:
        model = Conference
        fields = [
            'internal_external', 'title', 'conference_name', 'location',
            'lead_author', 'co_authors', 'lead_author_user', 'co_authors_users',
            'assigned_reviewers', 'status', 'abstract', 'paper',
            'submission_date', 'conference_date', 'decision_date'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'conference_name': forms.TextInput(attrs={'class': 'form-control'}),
            'location': forms.TextInput(attrs={'class': 'form-control'}),
            'lead_author': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Legacy field - use Lead Author (User) above'}),
            'co_authors': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Legacy field - use Co-Authors (Users) above'}),
            'abstract': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }

class ProjectForm(forms.ModelForm):
    class Meta:
        model = Project
        fields = ['name', 'description', 'project_type', 'status']