"""
Simplified test suite for manager app models
Tests focus on model instantiation and basic CRUD operations
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Paper, Conference, Template, ChangeLog, PaperStatusHistory, PaperComment

User = get_user_model()


class PaperModelTests(TestCase):
    """Test the Paper model"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='test123')
    
    def test_paper_creation(self):
        """Test creating a paper"""
        paper = Paper.objects.create(
            title='Test Paper',
            lead_author='Test Author',
            paper_type='journal',
            internal_external='internal',
            version='1.0',
            manuscript='test.pdf',
            created_by=self.user
        )
        self.assertEqual(paper.title, 'Test Paper')
        self.assertEqual(paper.lead_author, 'Test Author')


class ConferenceModelTests(TestCase):
    """Test the Conference model"""
    
    def test_conference_creation(self):
        """Test creating a conference"""
        conf = Conference.objects.create(
            title='Test Conference',
            internal_external='external'
        )
        self.assertEqual(conf.title, 'Test Conference')


class TemplateModelTests(TestCase):
    """Test the Template model"""
    
    def test_template_creation(self):
        """Test creating a template"""
        template = Template.objects.create(
            title='Test Template'
        )
        self.assertEqual(template.title, 'Test Template')


class ChangeLogTests(TestCase):
    """Test the ChangeLog model"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='test123')
    
    def test_changelog_creation(self):
        """Test creating a changelog entry"""
        log = ChangeLog.objects.create(
            content_type='paper',
            object_id=1,
            object_title='Test Paper',
            changed_by=self.user,
            field_name='title',
            field_label='Title',
            old_value='Old',
            new_value='New'
        )
        self.assertEqual(log.field_name, 'title')


class PaperStatusHistoryTests(TestCase):
    """Test the PaperStatusHistory model"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='test123')
        self.paper = Paper.objects.create(
            title='Test Paper',
            lead_author='Author',
            paper_type='journal',
            internal_external='internal',
            version='1.0',
            manuscript='test.pdf',
            created_by=self.user
        )
    
    def test_paper_status_history_creation(self):
        """Test creating a status history record"""
        history = PaperStatusHistory.objects.create(
            paper=self.paper,
            new_status='submitted',
            changed_by=self.user,
            reason='Submitted for review'
        )
        self.assertEqual(history.new_status, 'submitted')


class PaperCommentTests(TestCase):
    """Test the PaperComment model"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='test123')
        self.paper = Paper.objects.create(
            title='Test Paper',
            lead_author='Author',
            paper_type='journal',
            internal_external='internal',
            version='1.0',
            manuscript='test.pdf',
            created_by=self.user
        )
    
    def test_paper_comment_creation(self):
        """Test creating a paper comment"""
        comment = PaperComment.objects.create(
            paper=self.paper,
            user=self.user,
            text='This is a test comment'
        )
        self.assertEqual(comment.text, 'This is a test comment')
