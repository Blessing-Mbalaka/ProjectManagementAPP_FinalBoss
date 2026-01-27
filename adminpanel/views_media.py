"""
Custom Media Serving View
Serves media files with automatic fallback to database if filesystem file is missing.
Provides resilience for distributed deployments and disaster recovery.
"""

import os
import mimetypes
from django.http import FileResponse, HttpResponseNotFound
from django.views.decorators.http import condition
from django.conf import settings
from django.utils.http import parse_etags, quote_etag
from adminpanel.media_models import SystemMedia
from adminpanel.media_service import MediaService
from io import BytesIO


def get_media_file(request, path):
    """
    Serve media files with fallback to database.
    
    Flow:
    1. Try to serve from filesystem (/media/)
    2. If 404, check SystemMedia database
    3. If found in DB, stream from file_blob
    4. If not found anywhere, return 404
    
    Args:
        request: Django request object
        path: Relative path to file (e.g., 'submissions/file.pdf')
    
    Returns:
        FileResponse or HttpResponseNotFound
    """
    
    # Build full filesystem path
    full_path = os.path.join(settings.MEDIA_ROOT, path)
    
    # Try filesystem first
    if os.path.exists(full_path) and os.path.isfile(full_path):
        return serve_file_from_filesystem(full_path, path)
    
    # Filesystem file not found, try database fallback
    system_media = find_system_media_by_path(path)
    
    if system_media:
        if system_media.stored_in_db and system_media.file_blob:
            # File found in database, restore to filesystem and serve
            MediaService.restore_file_from_db_to_filesystem(system_media.id)
            # Try filesystem again
            if os.path.exists(full_path) and os.path.isfile(full_path):
                return serve_file_from_filesystem(full_path, path)
            # If restore failed, stream from database
            return serve_file_from_database(system_media, path)
        elif system_media.file and os.path.exists(system_media.file.path):
            # File path is different, serve from that location
            return serve_file_from_filesystem(system_media.file.path, path)
    
    # File not found anywhere
    return HttpResponseNotFound(f"Media file not found: {path}")


def serve_file_from_filesystem(full_path, relative_path):
    """
    Serve file directly from filesystem.
    
    Args:
        full_path: Absolute path to file
        relative_path: Relative path for content-disposition
    
    Returns:
        FileResponse
    """
    try:
        # Determine MIME type
        content_type, encoding = mimetypes.guess_type(full_path)
        if content_type is None:
            content_type = 'application/octet-stream'
        
        # Open and serve file
        response = FileResponse(
            open(full_path, 'rb'),
            content_type=content_type,
            as_attachment=False
        )
        
        # Set Content-Disposition header for display
        filename = os.path.basename(relative_path)
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        
        return response
    
    except Exception as e:
        return HttpResponseNotFound(f"Error serving file: {str(e)}")


def serve_file_from_database(system_media, path):
    """
    Serve file from database binary content.
    
    Args:
        system_media: SystemMedia instance
        path: Relative path for filename
    
    Returns:
        FileResponse
    """
    try:
        # Create file-like object from binary data
        file_obj = BytesIO(system_media.file_blob)
        
        # Determine MIME type
        content_type = system_media.mime_type or 'application/octet-stream'
        
        # Serve from memory
        response = FileResponse(
            file_obj,
            content_type=content_type,
            as_attachment=False
        )
        
        # Set Content-Disposition header
        filename = system_media.filename or os.path.basename(path)
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        response['X-Served-From'] = 'Database'  # Debug header
        
        return response
    
    except Exception as e:
        return HttpResponseNotFound(f"Error serving file from database: {str(e)}")


def find_system_media_by_path(path):
    """
    Find SystemMedia record by file path.
    Searches by:
    1. Exact file path in file field
    2. Filename match
    
    Args:
        path: Relative path to find
    
    Returns:
        SystemMedia instance or None
    """
    filename = os.path.basename(path)
    
    # Try to find by file path first
    system_media = SystemMedia.objects.filter(
        file=path,
        is_active=True
    ).first()
    
    if system_media:
        return system_media
    
    # Try by filename (in case path changed)
    system_media = SystemMedia.objects.filter(
        filename=filename,
        is_active=True
    ).first()
    
    return system_media


def media_file_last_modified(request, path):
    """
    Get last modified time for conditional requests (If-Modified-Since).
    Used by @condition decorator for caching.
    """
    full_path = os.path.join(settings.MEDIA_ROOT, path)
    
    if os.path.exists(full_path):
        return os.path.getmtime(full_path)
    
    # Check database
    system_media = find_system_media_by_path(path)
    if system_media:
        return system_media.updated_at.timestamp()
    
    return None


def media_file_etag(request, path):
    """
    Generate ETag for conditional requests (If-None-Match).
    Used by @condition decorator for caching.
    """
    full_path = os.path.join(settings.MEDIA_ROOT, path)
    
    if os.path.exists(full_path):
        try:
            size = os.path.getsize(full_path)
            mtime = os.path.getmtime(full_path)
            return f'"{size}-{mtime}"'
        except:
            pass
    
    # Use database SystemMedia ID as etag
    system_media = find_system_media_by_path(path)
    if system_media:
        return f'"db-{system_media.id}"'
    
    return None
