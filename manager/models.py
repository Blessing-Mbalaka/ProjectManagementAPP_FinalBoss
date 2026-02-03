# models.py in projects app
from django.db import models
from django.conf import settings
from django.db import models
from django.contrib.auth import get_user_model

class LearningContent(models.Model):
    title = models.CharField(max_length=200)
    type = models.CharField(max_length=50)
    platform = models.CharField(max_length=100, null=True, blank=True)
    platform_logo = models.URLField(null=True, blank=True)
    description = models.TextField()
    link = models.URLField()
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='learning_resources', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title


class Template(models.Model):
    CATEGORY_CHOICES = [
        ('Book', 'Book Templates'),
        ('Research', 'Research Papers'),
        ('Software', 'Software Development'),
    ]

    title = models.CharField(max_length=100)
    description = models.TextField()
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    file = models.FileField(upload_to='templates/')
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='uploaded_templates', null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
    

User = get_user_model()

class Paper(models.Model):
    PAPER_TYPE_CHOICES = [
        ('journal', 'Journal Article'),
        ('conference', 'Conference Paper'),
    ]

    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('in-progress', 'In Progress'),
        ('review', 'Internal Review'),
        ('submitted', 'Submitted'),
        ('accepted', 'Accepted'),
        ('published', 'Published'),
        ('rejected', 'Rejected'),
    ]

    paper_type = models.CharField(max_length=20, choices=PAPER_TYPE_CHOICES)
    internal_external = models.CharField(max_length=10, choices=[('internal', 'Internal'), ('external', 'External')])
    title = models.CharField(max_length=255)
    lead_author = models.CharField(max_length=255)
    co_authors = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES)
    version = models.CharField(max_length=10)
    abstract = models.TextField(blank=True, null=True)
    manuscript = models.FileField(upload_to='manuscripts/')
    target_journal = models.CharField(max_length=255, blank=True, null=True)
    submission_date = models.DateField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='papers', null=True, blank=True)
    reviewers = models.ManyToManyField(User, related_name='reviewed_papers', blank=True)

    def __str__(self):
        return self.title


class Book(models.Model):
    STATUS_CHOICES = [
        ('writing', 'Writing & Development'),
        ('submission', 'Journal Submission'),
        ('review', 'Peer Review'),
        ('production', 'In Production'),
        ('published', 'Published'),
    ]

    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='writing')
    due_date = models.DateField(blank=True, null=True)
    lead_author = models.CharField(max_length=255)
    publisher = models.CharField(max_length=255, blank=True, null=True)
    total_chapters = models.PositiveIntegerField(default=1)
    completed_chapters = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    def progress_percentage(self):
        if self.total_chapters > 0:
            return int((self.completed_chapters / self.total_chapters) * 100)
        return 0


class Chapter(models.Model):
    STATUS_CHOICES = [
        ('Draft', 'Draft'),
        ('In Progress', 'In Progress'),
        ('In Review', 'In Review'),
        ('Completed', 'Completed'),
    ]

    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='chapters')
    chapter_number = models.PositiveIntegerField()
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255)
    editor = models.CharField(max_length=255, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Draft')
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Chapter {self.chapter_number} - {self.title}"


class PaperComment(models.Model):
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Comment by {self.user.username} on {self.paper.title}"

