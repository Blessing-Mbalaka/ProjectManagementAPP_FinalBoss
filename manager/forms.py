from django import forms
from adminpanel.models import EngagementLog, FinancialProject
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
            'client_name',
            'entry_type',
            'contact_method',
            'engagement_date',
            'next_follow_up_date',
            'subject',
            'notes',
            'proposal_summary',
        ]
        widgets = {
            'project': forms.Select(attrs={'class': 'form-select'}),
            'client_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Only needed for a project without a client opportunity'}),
            'entry_type': forms.Select(attrs={'class': 'form-select'}),
            'contact_method': forms.Select(attrs={'class': 'form-select'}),
            'engagement_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'next_follow_up_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional topic or meeting title'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Add the meeting minutes, discussion summary, or client correspondence here.'}),
            'proposal_summary': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'What did your centre propose to the client?'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        allowed_projects = kwargs.pop('projects', None)
        super().__init__(*args, **kwargs)

        projects = Project.objects.all().select_related('research_centre').order_by('-created_at', 'name')

        if allowed_projects is not None:
            projects = allowed_projects
        elif user and getattr(user, 'research_centre_id', None):
            projects = projects.filter(research_centre_id=user.research_centre_id)

        self.fields['project'].queryset = projects
        self.fields['project'].label = 'Client / opportunity'
        self.fields['project'].help_text = 'Choose the client opportunity. A cost centre is linked automatically only after the bid is won and the official code is issued.'
        self.fields['project'].label_from_instance = self._project_label
        self.fields['client_name'].label = 'Client name (only if no opportunity exists)'

    @staticmethod
    def _project_label(project):
        try:
            financial = project.financial_project
        except FinancialProject.DoesNotExist:
            return project.name
        return f'{financial.client_name} — {project.name} ({financial.get_stage_display()})'

    def clean(self):
        cleaned = super().clean()
        project = cleaned.get('project')
        client_name = (cleaned.get('client_name') or '').strip()
        financial = None
        if project:
            financial = FinancialProject.objects.select_related('cost_centre').filter(project=project).first()
        if financial:
            cleaned['client_name'] = financial.client_name
            self.instance.client_name = financial.client_name
            self.instance.cost_centre = financial.cost_centre
        elif not client_name:
            self.add_error('client_name', 'Enter the client name for a project that has no client opportunity.')
        return cleaned
