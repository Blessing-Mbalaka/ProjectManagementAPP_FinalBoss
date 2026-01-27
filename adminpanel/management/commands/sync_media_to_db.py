"""
Management Command: sync_media_to_db
Synchronizes all existing files to database as backup.
Bulk backs up all media files to SystemMedia.file_blob field.
"""

import os
from django.core.management.base import BaseCommand
from django.conf import settings
from adminpanel.media_models import SystemMedia
from adminpanel.media_service import MediaService


class Command(BaseCommand):
    help = 'Sync all media files to database for backup/recovery'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be synced without making changes'
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force re-sync even if already stored in DB'
        )
        parser.add_argument(
            '--check-integrity',
            action='store_true',
            help='Verify filesystem and database copies match'
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run', False)
        force = options.get('force', False)
        check_integrity = options.get('check_integrity', False)
        
        self.stdout.write(self.style.SUCCESS("\n" + "="*70))
        self.stdout.write(self.style.SUCCESS("MEDIA SYNC TO DATABASE"))
        self.stdout.write(self.style.SUCCESS("="*70 + "\n"))
        
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN MODE: No changes will be made\n"))
        
        if check_integrity:
            self.check_media_integrity()
            return
        
        # Get all active SystemMedia records with files
        media_records = SystemMedia.objects.filter(is_active=True)
        
        if not force:
            media_records = media_records.filter(stored_in_db=False)
        
        total = media_records.count()
        synced = 0
        skipped = 0
        errors = 0
        
        self.stdout.write(f"Found {total} media files to sync\n")
        
        for i, media in enumerate(media_records, 1):
            try:
                # Get file path
                if not media.file:
                    self.stdout.write(
                        self.style.WARNING(f"[{i}/{total}] SKIP: {media.filename} - No file reference")
                    )
                    skipped += 1
                    continue
                
                file_path = media.file.path
                
                # Check if file exists
                if not os.path.exists(file_path):
                    self.stdout.write(
                        self.style.WARNING(f"[{i}/{total}] SKIP: {media.filename} - File not found on filesystem")
                    )
                    skipped += 1
                    continue
                
                # Skip if already synced and not forcing
                if media.stored_in_db and not force:
                    self.stdout.write(
                        self.style.WARNING(f"[{i}/{total}] SKIP: {media.filename} - Already in DB (use --force to override)")
                    )
                    skipped += 1
                    continue
                
                # Read file
                with open(file_path, 'rb') as f:
                    file_blob = f.read()
                
                file_size = len(file_blob)
                
                if not dry_run:
                    # Update database
                    media.file_blob = file_blob
                    media.stored_in_db = True
                    media.save()
                
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[{i}/{total}] SYNC: {media.filename} ({self._format_size(file_size)})"
                    )
                )
                synced += 1
                
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"[{i}/{total}] ERROR: {media.filename} - {str(e)}")
                )
                errors += 1
        
        # Summary
        self.stdout.write("\n" + "="*70)
        self.stdout.write(self.style.SUCCESS("SUMMARY"))
        self.stdout.write("="*70)
        self.stdout.write(f"Total files found: {total}")
        self.stdout.write(self.style.SUCCESS(f"Synced: {synced}"))
        self.stdout.write(self.style.WARNING(f"Skipped: {skipped}"))
        self.stdout.write(self.style.ERROR(f"Errors: {errors}"))
        
        if dry_run:
            self.stdout.write(self.style.WARNING("\nDRY RUN: No changes were made"))
        else:
            self.stdout.write(self.style.SUCCESS("\n✓ Sync complete"))
        
        self.stdout.write("="*70 + "\n")

    def check_media_integrity(self):
        """Verify filesystem and database copies match"""
        self.stdout.write(self.style.SUCCESS("CHECKING MEDIA INTEGRITY\n"))
        
        media_records = SystemMedia.objects.filter(
            is_active=True,
            stored_in_db=True
        )
        
        total = media_records.count()
        valid = 0
        mismatched = 0
        errors = 0
        
        self.stdout.write(f"Checking {total} media files\n")
        
        for i, media in enumerate(media_records, 1):
            try:
                if not media.file or not os.path.exists(media.file.path):
                    self.stdout.write(
                        self.style.WARNING(f"[{i}/{total}] MISSING: {media.filename} - Not on filesystem")
                    )
                    mismatched += 1
                    continue
                
                # Read filesystem file
                with open(media.file.path, 'rb') as f:
                    fs_content = f.read()
                
                # Compare with database
                if media.file_blob == fs_content:
                    self.stdout.write(
                        self.style.SUCCESS(f"[{i}/{total}] OK: {media.filename}")
                    )
                    valid += 1
                else:
                    self.stdout.write(
                        self.style.WARNING(f"[{i}/{total}] MISMATCH: {media.filename} - Files differ")
                    )
                    mismatched += 1
                    
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f"[{i}/{total}] ERROR: {media.filename} - {str(e)}")
                )
                errors += 1
        
        # Summary
        self.stdout.write("\n" + "="*70)
        self.stdout.write(self.style.SUCCESS("INTEGRITY CHECK SUMMARY"))
        self.stdout.write("="*70)
        self.stdout.write(self.style.SUCCESS(f"Valid: {valid}"))
        self.stdout.write(self.style.WARNING(f"Mismatched: {mismatched}"))
        self.stdout.write(self.style.ERROR(f"Errors: {errors}"))
        self.stdout.write("="*70 + "\n")

    def _format_size(self, size_bytes):
        """Format bytes to human readable"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} TB"
