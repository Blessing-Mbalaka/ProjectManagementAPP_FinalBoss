"""
Simplified test suite for projects app models
Tests focus on model instantiation and basic operations
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import Project, Task, StudentProfile, Submission, DailyTask

User = get_user_model()


class ProjectModelTests(TestCase):
    """Test the Project model"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='manager', password='test123', role='admin')
    
    def test_project_creation(self):
        """Test creating a project"""
        project = Project.objects.create(
            name='Test Project',
            project_type='software',
            status='planning',
            created_by=self.user
        )
        self.assertEqual(project.name, 'Test Project')
        self.assertEqual(project.project_type, 'software')


class TaskModelTests(TestCase):
    """Test the Task model"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='user', password='test123')
        self.project = Project.objects.create(
            name='Test Project',
            project_type='software',
            status='planning',
            created_by=self.user
        )
    
    def test_task_creation(self):
        """Test creating a task"""
        task = Task.objects.create(
            project=self.project,
            title='Test Task',
            status='todo',
            created_by=self.user
        )
        self.assertEqual(task.title, 'Test Task')
        self.assertEqual(task.status, 'todo')


class StudentProfileTests(TestCase):
    """Test the StudentProfile model"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='student', password='test123', role='employee')
    
    def test_student_profile_creation(self):
        """Test creating a student profile"""
        profile = StudentProfile.objects.create(
            user=self.user,
            program='Bachelor of Science',
            research_title='My Research'
        )
        self.assertEqual(profile.program, 'Bachelor of Science')


class SubmissionModelTests(TestCase):
    """Test the Submission model"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='student', password='test123')
    
    def test_submission_creation(self):
        """Test creating a submission"""
        submission = Submission.objects.create(
            student=self.user,
            document_type='Paper',
            title='Test Paper Submission',
            file='test.pdf'
        )
        self.assertEqual(submission.title, 'Test Paper Submission')
        self.assertEqual(submission.document_type, 'Paper')


class DailyTaskModelTests(TestCase):
    """Test the DailyTask model"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='user', password='test123')
    
    def test_daily_task_creation(self):
        """Test creating a daily task"""
        task = DailyTask.objects.create(
            user=self.user,
            title='Daily standup'
        )
        self.assertEqual(task.title, 'Daily standup')
        self.assertEqual(task.is_done, False)
