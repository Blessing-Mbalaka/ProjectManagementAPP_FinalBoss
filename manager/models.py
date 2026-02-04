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

    # Unified statuses work for both internal and external papers
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('circulation', 'In Circulation'),
        ('ready-submission', 'Ready for Submission'),
        ('returned-feedback', 'Returned with Feedback'),
        ('submitted', 'Submitted'),
        ('under-review', 'Under Review'),
        ('accepted', 'Accepted'),
        ('accepted-minor', 'Accepted - Minor Revisions'),
        ('accepted-major', 'Accepted - Major Revisions'),
        ('published', 'Published'),
        ('rejected', 'Rejected'),
    ]

    # Statuses shown for internal papers
    INTERNAL_STATUSES = ['draft', 'circulation', 'ready-submission', 'returned-feedback']
    # Statuses shown for external papers
    EXTERNAL_STATUSES = ['submitted', 'under-review', 'accepted', 'accepted-minor', 'accepted-major', 'published', 'rejected']

    paper_type = models.CharField(max_length=20, choices=PAPER_TYPE_CHOICES)
    internal_external = models.CharField(max_length=10, choices=[('internal', 'Internal'), ('external', 'External')])
    title = models.CharField(max_length=255)
    # Legacy text fields (for backward compatibility)
    lead_author = models.CharField(max_length=255)
    co_authors = models.TextField(blank=True, null=True)
    # New user reference fields
    lead_author_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lead_papers'
    )
    co_authors_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='co_authored_papers',
        blank=True
    )
    assigned_reviewers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='papers_to_review',
        blank=True
    )
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='draft')
    version = models.CharField(max_length=10)
    abstract = models.TextField(blank=True, null=True)
    manuscript = models.FileField(upload_to='manuscripts/')
    target_journal = models.CharField(max_length=255, blank=True, null=True)
    submission_date = models.DateField(blank=True, null=True)
    decision_date = models.DateField(blank=True, null=True)
    feedback_text = models.TextField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='papers', null=True, blank=True)
    reviewers = models.ManyToManyField(User, related_name='reviewed_papers', blank=True)

    def __str__(self):
        return self.title

    def get_available_statuses(self):
        """Return available statuses based on internal/external type"""
        if self.internal_external == 'internal':
            return [s for s in self.STATUS_CHOICES if s[0] in self.INTERNAL_STATUSES]
        else:
            return [s for s in self.STATUS_CHOICES if s[0] in self.EXTERNAL_STATUSES]

    def get_lead_author_display(self):
        """Display lead author, preferring user reference over legacy text field"""
        if self.lead_author_user:
            return self.lead_author_user.get_full_name() or self.lead_author_user.username
        return self.lead_author

    def get_all_authors(self):
        """Get all authors as a set: lead author + co-authors"""
        authors = set()
        if self.lead_author_user:
            authors.add(self.lead_author_user)
        authors.update(self.co_authors_users.all())
        return authors

    def get_all_contributors(self):
        """Get all users involved: authors + creator + assigned reviewers"""
        contributors = self.get_all_authors()
        if self.created_by:
            contributors.add(self.created_by)
        contributors.update(self.assigned_reviewers.all())
        return contributors


class PaperStatusHistory(models.Model):
    """Track all status changes to papers for audit trail"""
    paper = models.ForeignKey(Paper, on_delete=models.CASCADE, related_name='status_history')
    old_status = models.CharField(max_length=50, null=True, blank=True)
    new_status = models.CharField(max_length=50)
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)
    reason = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-changed_at']
    
    def __str__(self):
        return f"{self.paper.title}: {self.old_status} → {self.new_status} ({self.changed_at})"


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


class Conference(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Draft'),
        ('in-progress', 'In Progress'),
        ('submitted', 'Submitted'),
        ('accepted', 'Accepted'),
        ('presenting', 'Presenting'),
        ('presented', 'Presented'),
        ('rejected', 'Rejected'),
    ]

    internal_external = models.CharField(
        max_length=10, 
        choices=[('internal', 'Internal'), ('external', 'External')]
    )
    title = models.CharField(max_length=255)
    conference_name = models.CharField(max_length=255)
    location = models.CharField(max_length=255, blank=True, null=True)
    # Legacy text fields (for backward compatibility)
    lead_author = models.CharField(max_length=255)
    co_authors = models.TextField(blank=True, null=True)
    # New user reference fields
    lead_author_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='lead_conferences'
    )
    co_authors_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='co_authored_conferences',
        blank=True
    )
    assigned_reviewers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name='conferences_to_review',
        blank=True
    )
    status = models.CharField(max_length=50, choices=STATUS_CHOICES)
    abstract = models.TextField(blank=True, null=True)
    paper = models.FileField(upload_to='conference_papers/', blank=True, null=True)
    submission_date = models.DateField(blank=True, null=True)
    conference_date = models.DateField(blank=True, null=True)
    decision_date = models.DateField(blank=True, null=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='conferences', null=True, blank=True)
    reviewers = models.ManyToManyField(User, related_name='reviewed_conferences', blank=True)

    def __str__(self):
        return self.title

    def get_lead_author_display(self):
        """Display lead author, preferring user reference over legacy text field"""
        if self.lead_author_user:
            return self.lead_author_user.get_full_name() or self.lead_author_user.username
        return self.lead_author

    def get_all_authors(self):
        """Get all authors as a set: lead author + co-authors"""
        authors = set()
        if self.lead_author_user:
            authors.add(self.lead_author_user)
        authors.update(self.co_authors_users.all())
        return authors

    def get_all_contributors(self):
        """Get all users involved: authors + creator + assigned reviewers"""
        contributors = self.get_all_authors()
        if self.created_by:
            contributors.add(self.created_by)
        contributors.update(self.assigned_reviewers.all())
        return contributors

    class Meta:
        ordering = ['-updated_at']

class ChangeLog(models.Model):
    """Track changes to Papers and Conferences for audit trail and notifications"""
    CONTENT_TYPE_CHOICES = [
        ('paper', 'Research Paper'),
        ('conference', 'Conference'),
    ]
    
    content_type = models.CharField(max_length=20, choices=CONTENT_TYPE_CHOICES)
    object_id = models.IntegerField()
    object_title = models.CharField(max_length=500, null=True, blank=True)
    
    changed_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='changes_made')
    changed_at = models.DateTimeField(auto_now_add=True)
    
    field_name = models.CharField(max_length=100)  # e.g., 'title', 'status', 'lead_author_user'
    field_label = models.CharField(max_length=100)  # Human-readable label
    old_value = models.TextField(null=True, blank=True)
    new_value = models.TextField(null=True, blank=True)
    
    class Meta:
        ordering = ['-changed_at']
        indexes = [
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['changed_by']),
            models.Index(fields=['-changed_at']),
        ]
    
    def __str__(self):
        return f"{self.get_content_type_display()} - {self.field_label} changed at {self.changed_at}"
    
    @classmethod
    def log_change(cls, content_type, obj, field_name, field_label, old_value, new_value, changed_by):
        """Helper method to log a single field change"""
        return cls.objects.create(
            content_type=content_type,
            object_id=obj.id,
            object_title=str(obj),
            changed_by=changed_by,
            field_name=field_name,
            field_label=field_label,
            old_value=str(old_value) if old_value is not None else None,
            new_value=str(new_value) if new_value is not None else None,
        )
    
    @classmethod
    def get_recent_changes(cls, content_type, object_id, limit=10):
        """Get recent changes for a specific object"""
        return cls.objects.filter(
            content_type=content_type,
            object_id=object_id
        ).order_by('-changed_at')[:limit]