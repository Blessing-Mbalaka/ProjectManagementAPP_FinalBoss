"""
System Media Model
Tracks all uploaded media files in the database for audit trail and organization.
Supports flexible relationships to any model via GenericForeignKey.
"""

from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from users.models import CustomUser


class SystemMedia(models.Model):
    """
    Model to track all media files uploaded to the system.
    Provides audit trail and centralized media management.
    Supports relationships to any model via GenericForeignKey.
    """
    
    # Media file reference
    file = models.FileField(
        upload_to='system_media/%Y/%m/%d/',
        help_text='The actual media file'
    )
    
    # File metadata
    filename = models.CharField(
        max_length=255,
        help_text='Original filename'
    )
    file_type = models.CharField(
        max_length=50,
        choices=[
            ('image', 'Image'),
            ('document', 'Document'),
            ('video', 'Video'),
            ('audio', 'Audio'),
            ('archive', 'Archive'),
            ('other', 'Other'),
        ],
        default='other'
    )
    file_size = models.BigIntegerField(
        help_text='File size in bytes',
        null=True,
        blank=True
    )
    
    # Upload information
    uploaded_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_media'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    # File metadata
    mime_type = models.CharField(
        max_length=100,
        blank=True,
        help_text='MIME type of the file'
    )
    
    # Status tracking
    is_active = models.BooleanField(
        default=True,
        help_text='Whether this media is still in use'
    )
    
    # Optional description
    description = models.TextField(
        blank=True,
        help_text='Description of the media file'
    )
    
    # Purpose tracking (how file is used in system)
    PURPOSE_CHOICES = [
        ('submission', 'Student Submission'),
        ('feedback', 'Supervisor Feedback'),
        ('template', 'Project Template'),
        ('manuscript', 'Paper Manuscript'),
        ('progress_update', 'Progress Update'),
        ('general', 'General Upload'),
    ]
    purpose = models.CharField(
        max_length=50,
        choices=PURPOSE_CHOICES,
        default='general',
        help_text='Purpose/use of the file in system'
    )
    
    # Generic relationship support - link to any model
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='system_media_files',
        help_text='Content type of the related object'
    )
    object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='ID of the related object'
    )
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text='Soft delete timestamp'
    )
    
    # Dual-storage fields - backup to database
    file_blob = models.BinaryField(
        null=True,
        blank=True,
        help_text='File content stored in database (for fallback/backup)'
    )
    stored_in_db = models.BooleanField(
        default=False,
        help_text='Whether file is backed up in database'
    )
    
    class Meta:
        verbose_name = 'System Media'
        verbose_name_plural = 'System Media'
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['uploaded_by', '-uploaded_at']),
            models.Index(fields=['file_type']),
            models.Index(fields=['is_active']),
            models.Index(fields=['purpose']),
            models.Index(fields=['content_type', 'object_id']),
        ]
    
    def __str__(self):
        return f"{self.filename} ({self.get_file_type_display()})"
    
    def get_file_size_display(self):
        """Convert bytes to human-readable format"""
        if self.file_size is None:
            return "Unknown"
        
        size = float(self.file_size)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} TB"
    
    def save(self, *args, **kwargs):
        """Override save to set filename and file_size"""
        if self.file and not self.filename:
            self.filename = self.file.name
        
        if self.file and not self.file_size:
            try:
                self.file_size = self.file.size
            except:
                pass
        
        super().save(*args, **kwargs)
    
    @property
    def uploader_name(self):
        """Get uploader's full name"""
        if self.uploaded_by:
            return self.uploaded_by.get_full_name() or self.uploaded_by.username
        return "System"
    
    @property
    def related_object_display(self):
        """Display the related object as string if available"""
        if self.content_object:
            return str(self.content_object)
        return "No related object"
    
    @property
    def related_model_name(self):
        """Get the model name of the related object"""
        if self.content_type:
            return self.content_type.model
        return None
