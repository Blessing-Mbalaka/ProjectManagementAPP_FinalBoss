"""
Media Service Utility
Handles unified media file uploads and automatic SystemMedia record creation.
Provides a centralized interface for file handling across all apps.
"""

import os
import mimetypes
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from .media_models import SystemMedia


class MediaService:
    """
    Service for handling media file uploads and tracking.
    Automatically creates SystemMedia records for all uploads.
    """
    
    # File type mapping based on MIME type
    FILE_TYPE_MAPPING = {
        'image': ['image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml'],
        'document': ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain'],
        'video': ['video/mp4', 'video/mpeg', 'video/quicktime', 'video/x-msvideo'],
        'audio': ['audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/flac'],
        'archive': ['application/zip', 'application/x-rar-compressed', 'application/x-7z-compressed'],
    }
    
    @staticmethod
    def get_file_type(mime_type):
        """Determine file type from MIME type"""
        if not mime_type:
            return 'other'
        
        for file_type, mime_types in MediaService.FILE_TYPE_MAPPING.items():
            if mime_type in mime_types:
                return file_type
        
        # Check by prefix
        if mime_type.startswith('image/'):
            return 'image'
        elif mime_type.startswith('video/'):
            return 'video'
        elif mime_type.startswith('audio/'):
            return 'audio'
        
        return 'other'
    
    @staticmethod
    def guess_mime_type(filename):
        """Guess MIME type from filename"""
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type or 'application/octet-stream'
    
    @staticmethod
    def create_media_record(
        file_obj,
        uploaded_by,
        purpose='general',
        description='',
        related_object=None,
        filename=None
    ):
        """
        Create a SystemMedia record for an uploaded file.
        
        Args:
            file_obj: The file object from request.FILES
            uploaded_by: CustomUser instance who uploaded the file
            purpose: Purpose of the file (submission, feedback, template, etc.)
            description: Optional description
            related_object: Related model instance (Submission, Template, etc.)
            filename: Custom filename (defaults to file_obj.name)
        
        Returns:
            SystemMedia instance
        """
        # Determine filename
        actual_filename = filename or file_obj.name
        
        # Guess MIME type
        mime_type = MediaService.guess_mime_type(actual_filename)
        file_type = MediaService.get_file_type(mime_type)
        
        # Prepare SystemMedia data
        media_data = {
            'file': file_obj,
            'filename': actual_filename,
            'file_type': file_type,
            'mime_type': mime_type,
            'uploaded_by': uploaded_by,
            'purpose': purpose,
            'description': description,
        }
        
        # Add generic relationship if related object provided
        if related_object:
            content_type = ContentType.objects.get_for_model(related_object.__class__)
            media_data['content_type'] = content_type
            media_data['object_id'] = related_object.pk
        
        # Create and return SystemMedia record
        system_media = SystemMedia.objects.create(**media_data)
        return system_media
    
    @staticmethod
    def create_media_record_with_backup(
        file_obj,
        uploaded_by,
        purpose='general',
        description='',
        related_object=None,
        filename=None,
        backup_to_db=True
    ):
        """
        Create a SystemMedia record AND optionally backup file to database.
        Dual-storage: filesystem + optional database backup.
        
        Args:
            file_obj: The file object from request.FILES
            uploaded_by: CustomUser instance who uploaded the file
            purpose: Purpose of the file
            description: Optional description
            related_object: Related model instance
            filename: Custom filename (defaults to file_obj.name)
            backup_to_db: Whether to store file binary in database (default: True)
        
        Returns:
            SystemMedia instance
        """
        # Determine filename
        actual_filename = filename or file_obj.name
        
        # Guess MIME type
        mime_type = MediaService.guess_mime_type(actual_filename)
        file_type = MediaService.get_file_type(mime_type)
        
        # Read file content for database backup
        file_blob = None
        if backup_to_db:
            try:
                file_obj.seek(0)  # Reset to beginning
                file_blob = file_obj.read()
                file_obj.seek(0)  # Reset again for filesystem storage
            except Exception as e:
                print(f"Warning: Could not read file for backup: {e}")
                file_blob = None
        
        # Prepare SystemMedia data
        media_data = {
            'file': file_obj,
            'filename': actual_filename,
            'file_type': file_type,
            'mime_type': mime_type,
            'uploaded_by': uploaded_by,
            'purpose': purpose,
            'description': description,
            'file_blob': file_blob,
            'stored_in_db': backup_to_db and file_blob is not None,
        }
        
        # Add generic relationship if related object provided
        if related_object:
            content_type = ContentType.objects.get_for_model(related_object.__class__)
            media_data['content_type'] = content_type
            media_data['object_id'] = related_object.pk
        
        # Create and return SystemMedia record
        system_media = SystemMedia.objects.create(**media_data)
        return system_media
    
    @staticmethod
    def link_existing_file(
        file_path,
        uploaded_by,
        purpose='general',
        description='',
        related_object=None
    ):
        """
        Create SystemMedia record for an existing file (migration scenario).
        
        Args:
            file_path: Relative path to file in MEDIA_ROOT
            uploaded_by: CustomUser instance
            purpose: Purpose of the file
            description: Optional description
            related_object: Related model instance
        
        Returns:
            SystemMedia instance
        """
        from django.conf import settings
        
        # Get full path
        full_path = os.path.join(settings.MEDIA_ROOT, file_path)
        
        # Check if file exists
        if not os.path.exists(full_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # Get file size
        file_size = os.path.getsize(full_path)
        
        # Get MIME type and file type
        mime_type = MediaService.guess_mime_type(file_path)
        file_type = MediaService.get_file_type(mime_type)
        
        # Get filename
        filename = os.path.basename(file_path)
        
        # Prepare data
        media_data = {
            'filename': filename,
            'file_type': file_type,
            'mime_type': mime_type,
            'file_size': file_size,
            'uploaded_by': uploaded_by,
            'purpose': purpose,
            'description': description,
        }
        
        # Add generic relationship if provided
        if related_object:
            content_type = ContentType.objects.get_for_model(related_object.__class__)
            media_data['content_type'] = content_type
            media_data['object_id'] = related_object.pk
        
        # Create SystemMedia and manually set file path
        system_media = SystemMedia(**media_data)
        system_media.file.name = file_path  # Set the relative file path
        system_media.save()
        
        return system_media
    
    @staticmethod
    def update_media_status(system_media_id, is_active):
        """Update media active status"""
        system_media = SystemMedia.objects.get(pk=system_media_id)
        system_media.is_active = is_active
        system_media.save()
        return system_media
    
    @staticmethod
    def soft_delete_media(system_media_id):
        """Soft delete a media record"""
        from django.utils import timezone
        
        system_media = SystemMedia.objects.get(pk=system_media_id)
        system_media.deleted_at = timezone.now()
        system_media.is_active = False
        system_media.save()
        return system_media
    
    @staticmethod
    def get_file_type_from_extension(filename):
        """Determine file type from file extension"""
        extensions = {
            'image': ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg'],
            'document': ['.pdf', '.doc', '.docx', '.txt', '.txt'],
            'video': ['.mp4', '.mpeg', '.mov', '.avi'],
            'audio': ['.mp3', '.wav', '.ogg', '.flac'],
            'archive': ['.zip', '.rar', '.7z', '.tar', '.gz'],
        }
        
        _, ext = os.path.splitext(filename.lower())
        
        for file_type, exts in extensions.items():
            if ext in exts:
                return file_type
        
        return 'other'
    
    @staticmethod
    def get_file_from_db(system_media_id):
        """
        Retrieve file content from database backup.
        
        Args:
            system_media_id: SystemMedia primary key
        
        Returns:
            File content (bytes) or None if not stored
        """
        try:
            system_media = SystemMedia.objects.get(pk=system_media_id)
            if system_media.stored_in_db and system_media.file_blob:
                return system_media.file_blob
        except SystemMedia.DoesNotExist:
            pass
        return None
    
    @staticmethod
    def restore_file_from_db_to_filesystem(system_media_id):
        """
        Restore file from database to filesystem if missing.
        Used for recovery/migration scenarios.
        
        Args:
            system_media_id: SystemMedia primary key
        
        Returns:
            True if restored successfully, False otherwise
        """
        from django.conf import settings
        
        try:
            system_media = SystemMedia.objects.get(pk=system_media_id)
            
            if not system_media.file_blob:
                return False
            
            # Check if file missing from filesystem
            file_path = system_media.file.path if system_media.file else None
            if not file_path or not os.path.exists(file_path):
                # Restore from blob
                if system_media.file:
                    # File path exists in DB
                    directory = os.path.dirname(file_path)
                    os.makedirs(directory, exist_ok=True)
                    
                    with open(file_path, 'wb') as f:
                        f.write(system_media.file_blob)
                    
                    return True
        except Exception as e:
            print(f"Error restoring file: {e}")
        
        return False
