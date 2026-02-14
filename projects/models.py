from django.db import models
from django.conf import settings
from adminpanel.models import SupervisorProfile

class Project(models.Model):
    PROJECT_TYPES = (
        ('software', 'Software Project'),
        ('book', 'Book Project'),
        ('paper', 'Paper'),
    )
   
    STATUS_CHOICES = (
        ('planning', 'Planning'),
        ('in-progress', 'In Progress'),
        ('on-hold', 'On Hold'),
        ('completed', 'Completed'),
    )
   
    name = models.CharField(max_length=255)
    description = models.TextField(max_length=255, blank=True, null=True)
    project_type = models.CharField(max_length=20, choices=PROJECT_TYPES, default='software')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='planning')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_projects')
    created_at = models.DateTimeField(auto_now_add=True)
    due_date = models.DateField(blank=True, null=True)
    assigned_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assigned_projects', null=True, blank=True)

    def __str__(self):
        return self.name


class Task(models.Model):
    PROJECT_PHASES = [
        ('UX/UI', 'UX/UI'),
        ('Architecture', 'Architecture'),
        ('Frontend', 'Frontend'),
        ('Backend', 'Backend'),
        ('Testing', 'Testing'),
        ('Deployment', 'Deployment'),
        ('Paper', 'Paper'),
        ('Book', 'Book'),
        ('Other', 'Other'),
    ]

    PRIORITY_CHOICES = [
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
    ]

    STATUS_CHOICES = [
        ('todo', 'To Do'),
        ('in_progress', 'In Progress'),
        ('review', 'Review'),
        ('done', 'Done'),
    ]

    # Map task status to progress percentage
    STATUS_TO_PROGRESS = {
        'todo': 0,
        'in_progress': 33,
        'review': 66,
        'done': 100,
    }

    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='tasks', null=True, blank=True)
    parent_task = models.ForeignKey('self', null=True, blank=True, related_name='subtasks', on_delete=models.CASCADE)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assigned_tasks', null=True, blank=True)
    title = models.CharField(max_length=255)
    status = models.CharField(choices=STATUS_CHOICES, default='todo', max_length=20)
    task_type = models.CharField(max_length=50, choices=PROJECT_PHASES, blank=True, null=True)
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, blank=True, null=True)
    due_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='created_tasks', null=True, blank=True)
    progress = models.IntegerField(default=0, help_text="Progress in percentage (0-100)")
    
    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """Auto-calculate progress based on task status"""
        # Map status to progress percentage
        if self.status in self.STATUS_TO_PROGRESS:
            self.progress = self.STATUS_TO_PROGRESS[self.status]
        
        super().save(*args, **kwargs)

    
class DailyTask(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    is_done = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
    
class StudentProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    supervisor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='supervised_students', limit_choices_to={'role__in': ['admin', 'supervisor']})
    program = models.CharField(max_length=100)
    co_supervisor = models.CharField(max_length=100, blank=True, null=True)
    research_title = models.CharField(max_length=255)
    year = models.CharField(max_length=50) 
    
    def __str__(self):
        return self.user.get_full_name()
    

class Submission(models.Model):
    DOCUMENT_TYPES = [
        ('Paper', 'Paper'),
        ('Chapter', 'Chapter'),
        ('Proposal', 'Proposal'),
        ('Thesis', 'Thesis'),
        ('Report', 'Report'),
        ('Other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('Pending Review', 'Pending Review'),
        ('Approved', 'Approved'),
        ('Feedback Provided', 'Feedback Provided'),
        ('Rejected', 'Rejected'),
    ]

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPES)
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='submissions/')
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='Pending Review')
    created_at = models.DateTimeField(auto_now_add=True)
    feedback_text = models.TextField(blank=True, null=True)
    feedback_file = models.FileField(upload_to='feedback/', blank=True, null=True)
    version_number = models.IntegerField(default=1)


    def __str__(self):
        return f"{self.student.get_full_name()} - {self.title}"
    
class FeedbackReply(models.Model):
    submission = models.ForeignKey('Submission', on_delete=models.CASCADE, related_name='replies')
    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.get_full_name()} replied on {self.created_at.strftime('%Y-%m-%d')}"

class Notification(models.Model):
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=255)
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.recipient.username} - {self.title}"
    
class Meeting(models.Model):
    MODE_CHOICES = [
        ('In-person', 'In-person'),
        ('Virtual', 'Virtual'),
    ]

    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Confirmed', 'Confirmed'),
        ('Completed', 'Completed'),
        ('Cancelled', 'Cancelled'),
    ]

    student = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    date = models.DateField()
    time = models.TimeField()
    duration = models.IntegerField(help_text="Duration in minutes")
    purpose = models.TextField()
    mode = models.CharField(max_length=20, choices=MODE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.student.get_full_name()} – {self.date} @ {self.time}"

class ChatMessage(models.Model):
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='sent_messages')
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='received_messages', null=True, blank=True)
    submission = models.ForeignKey('Submission', on_delete=models.CASCADE, related_name='chat_messages', null=True, blank=True)
    message = models.TextField()
    attachment = models.FileField(upload_to='messages/', blank=True, null=True, help_text='Optional file attachment')
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.sender.get_full_name()} – {self.timestamp.strftime('%H:%M')}"


class TeamMember(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    full_name = models.CharField(max_length=255)
    role = models.CharField(max_length=100)
   
    def __str__(self):
        return self.full_name or self.user.get_full_name()

class Assignment(models.Model):
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name='assignments')
    team_member = models.ForeignKey(TeamMember, on_delete=models.CASCADE)
    responsibility = models.TextField()
    assigned_at = models.DateTimeField(auto_now_add=True)
   
    class Meta:
        unique_together = ('project', 'team_member')
   
    def __str__(self):
        return f"{self.team_member} on {self.project}"

class ProgressUpdate(models.Model):
    task = models.ForeignKey(Task, on_delete=models.CASCADE)
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    file = models.FileField(upload_to='uploads/')
    comments = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
