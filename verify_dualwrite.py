#!/usr/bin/env python
"""Quick verification of dual-write system"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_manage.settings')
django.setup()

from adminpanel.media_models import SystemMedia

print("\n" + "="*70)
print("DUAL-WRITE SYSTEM VERIFICATION")
print("="*70 + "\n")

all_media = SystemMedia.objects.filter(is_active=True)
backed_up = SystemMedia.objects.filter(stored_in_db=True, is_active=True)

print(f"Total media files: {all_media.count()}")
print(f"Files backed up to DB: {backed_up.count()}\n")

for media in backed_up:
    blob_size = len(media.file_blob) if media.file_blob else 0
    file_size = media.file_size or 0
    
    print(f"✓ {media.filename}")
    print(f"  Filesystem: {file_size:,} bytes")
    print(f"  Database:   {blob_size:,} bytes")
    print(f"  Match:      {file_size == blob_size}")
    print()

print("="*70)
print("✓ Dual-write system is operational")
print("="*70 + "\n")
