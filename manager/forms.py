from django import forms
from adminpanel.models import CostCentre, EngagementLog
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


class EngagementLogForm(forms.ModelForm):
    class Meta:
        model = EngagementLog
        fields = [
            'project',
            'cost_centre',
            'entry_type',
            'engagement_date',
            'subject',
            'notes',
            'proposal_summary',
        ]
        widgets = {
            'project': forms.Select(attrs={'class': 'form-select'}),
            'cost_centre': forms.Select(attrs={'class': 'form-select'}),
            'entry_type': forms.Select(attrs={'class': 'form-select'}),
            'engagement_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional topic or meeting title'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Add the meeting minutes, discussion summary, or client correspondence here.'}),
            'proposal_summary': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'What did your centre propose to the client?'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        projects = Project.objects.all().select_related('research_centre').order_by('-created_at', 'name')
        cost_centres = CostCentre.objects.select_related('research_centre').order_by('name')

        if user and getattr(user, 'research_centre_id', None):
            projects = projects.filter(research_centre_id=user.research_centre_id)
            cost_centres = cost_centres.filter(research_centre_id=user.research_centre_id)

        self.fields['project'].queryset = projects
        self.fields['cost_centre'].queryset = cost_centres
