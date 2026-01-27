"""
Management command to migrate existing files to SystemMedia records.
This command creates SystemMedia entries for all existing FileField uploads.
"""

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from adminpanel.media_service import MediaService
from projects.models import Submission
from manager.models import Template, Paper
from adminpanel.models import SupervisorFeedback
import os

CustomUser = get_user_model()


class Command(BaseCommand):
    help = 'Migrate existing files to SystemMedia records for centralized tracking'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be migrated without actually creating records',
        )

    def handle(self, *args, **options):
        dry_run = options.get('dry_run')
        
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN MODE: No records will be created'))
            self.stdout.write('')

        created_count = 0
        skipped_count = 0

        # Migrate Submission files
        self.stdout.write(self.style.SUCCESS('Migrating Submission files...'))
        submissions = Submission.objects.filter(file__isnull=False).exclude(file='')
        
        for submission in submissions:
            try:
                # Check if SystemMedia record already exists
                from adminpanel.media_models import SystemMedia
                from django.contrib.contenttypes.models import ContentType
                
                content_type = ContentType.objects.get_for_model(Submission)
                existing = SystemMedia.objects.filter(
                    content_type=content_type,
                    object_id=submission.pk,
                    purpose='submission'
                ).exists()
                
                if existing:
                    self.stdout.write(f"  ⊘ SKIPPED: {submission.file.name} (already migrated)")
                    skipped_count += 1
                    continue
                
                if not dry_run:
                    MediaService.link_existing_file(
                        file_path=submission.file.name,
                        uploaded_by=submission.student,
                        purpose='submission',
                        description=f"Submission: {submission.title} (v{submission.version_number})",
                        related_object=submission
                    )
                    self.stdout.write(self.style.SUCCESS(f"  ✓ Created: {submission.file.name}"))
                    created_count += 1
                else:
                    self.stdout.write(f"  → Would create: {submission.file.name}")
                    created_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ ERROR: {submission.file.name} - {str(e)}"))
                skipped_count += 1

        # Migrate Submission feedback files
        self.stdout.write(self.style.SUCCESS('\nMigrating Submission feedback files...'))
        submissions_with_feedback = Submission.objects.filter(feedback_file__isnull=False).exclude(feedback_file='')
        
        for submission in submissions_with_feedback:
            try:
                from adminpanel.media_models import SystemMedia
                from django.contrib.contenttypes.models import ContentType
                
                content_type = ContentType.objects.get_for_model(Submission)
                existing = SystemMedia.objects.filter(
                    content_type=content_type,
                    object_id=submission.pk,
                    purpose='feedback'
                ).exists()
                
                if existing:
                    self.stdout.write(f"  ⊘ SKIPPED: {submission.feedback_file.name} (already migrated)")
                    skipped_count += 1
                    continue
                
                if not dry_run:
                    MediaService.link_existing_file(
                        file_path=submission.feedback_file.name,
                        uploaded_by=submission.student,  # Ideally this should be the supervisor
                        purpose='feedback',
                        description=f"Feedback for: {submission.title}",
                        related_object=submission
                    )
                    self.stdout.write(self.style.SUCCESS(f"  ✓ Created: {submission.feedback_file.name}"))
                    created_count += 1
                else:
                    self.stdout.write(f"  → Would create: {submission.feedback_file.name}")
                    created_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ ERROR: {submission.feedback_file.name} - {str(e)}"))
                skipped_count += 1

        # Migrate SupervisorFeedback files
        self.stdout.write(self.style.SUCCESS('\nMigrating SupervisorFeedback files...'))
        feedback_files = SupervisorFeedback.objects.filter(uploaded_file__isnull=False).exclude(uploaded_file='')
        
        for feedback in feedback_files:
            try:
                from adminpanel.media_models import SystemMedia
                from django.contrib.contenttypes.models import ContentType
                
                content_type = ContentType.objects.get_for_model(SupervisorFeedback)
                existing = SystemMedia.objects.filter(
                    content_type=content_type,
                    object_id=feedback.pk,
                    purpose='feedback'
                ).exists()
                
                if existing:
                    self.stdout.write(f"  ⊘ SKIPPED: {feedback.uploaded_file.name} (already migrated)")
                    skipped_count += 1
                    continue
                
                if not dry_run:
                    MediaService.link_existing_file(
                        file_path=feedback.uploaded_file.name,
                        uploaded_by=feedback.supervisor.user,
                        purpose='feedback',
                        description=f"Feedback document from supervisor",
                        related_object=feedback
                    )
                    self.stdout.write(self.style.SUCCESS(f"  ✓ Created: {feedback.uploaded_file.name}"))
                    created_count += 1
                else:
                    self.stdout.write(f"  → Would create: {feedback.uploaded_file.name}")
                    created_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ ERROR: {feedback.uploaded_file.name} - {str(e)}"))
                skipped_count += 1

        # Migrate Template files
        self.stdout.write(self.style.SUCCESS('\nMigrating Template files...'))
        templates = Template.objects.filter(file__isnull=False).exclude(file='')
        
        for template in templates:
            try:
                from adminpanel.media_models import SystemMedia
                from django.contrib.contenttypes.models import ContentType
                
                content_type = ContentType.objects.get_for_model(Template)
                existing = SystemMedia.objects.filter(
                    content_type=content_type,
                    object_id=template.pk,
                    purpose='template'
                ).exists()
                
                if existing:
                    self.stdout.write(f"  ⊘ SKIPPED: {template.file.name} (already migrated)")
                    skipped_count += 1
                    continue
                
                if not dry_run:
                    MediaService.link_existing_file(
                        file_path=template.file.name,
                        uploaded_by=template.uploaded_by,
                        purpose='template',
                        description=f"Template: {template.title} ({template.category})",
                        related_object=template
                    )
                    self.stdout.write(self.style.SUCCESS(f"  ✓ Created: {template.file.name}"))
                    created_count += 1
                else:
                    self.stdout.write(f"  → Would create: {template.file.name}")
                    created_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ ERROR: {template.file.name} - {str(e)}"))
                skipped_count += 1

        # Migrate Paper manuscripts
        self.stdout.write(self.style.SUCCESS('\nMigrating Paper manuscripts...'))
        papers = Paper.objects.filter(manuscript__isnull=False).exclude(manuscript='')
        
        for paper in papers:
            try:
                from adminpanel.media_models import SystemMedia
                from django.contrib.contenttypes.models import ContentType
                
                content_type = ContentType.objects.get_for_model(Paper)
                existing = SystemMedia.objects.filter(
                    content_type=content_type,
                    object_id=paper.pk,
                    purpose='manuscript'
                ).exists()
                
                if existing:
                    self.stdout.write(f"  ⊘ SKIPPED: {paper.manuscript.name} (already migrated)")
                    skipped_count += 1
                    continue
                
                if not dry_run:
                    MediaService.link_existing_file(
                        file_path=paper.manuscript.name,
                        uploaded_by=paper.created_by,
                        purpose='manuscript',
                        description=f"Manuscript: {paper.title}",
                        related_object=paper
                    )
                    self.stdout.write(self.style.SUCCESS(f"  ✓ Created: {paper.manuscript.name}"))
                    created_count += 1
                else:
                    self.stdout.write(f"  → Would create: {paper.manuscript.name}")
                    created_count += 1
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"  ✗ ERROR: {paper.manuscript.name} - {str(e)}"))
                skipped_count += 1

        # Summary
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f"Created: {created_count} SystemMedia records")
        self.stdout.write(f"Skipped: {skipped_count} records")
        self.stdout.write(self.style.SUCCESS('=' * 60))
        
        if dry_run:
            self.stdout.write(self.style.WARNING('\nDRY RUN COMPLETE: Run without --dry-run to actually create records'))
