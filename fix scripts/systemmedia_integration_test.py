"""
SystemMedia Integration Test Suite
Tests MediaService functionality and SystemMedia relationships.
Run with: python manage.py test systemmedia_integration_test
Or directly: python systemmedia_integration_test.py
"""

import os
import sys
import django
from io import BytesIO

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_manage.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from projects.models import Submission, StudentProfile
from manager.models import Template, Paper
from adminpanel.models import SupervisorProfile, SupervisorFeedback
from adminpanel.media_models import SystemMedia
from adminpanel.media_service import MediaService

CustomUser = get_user_model()


class MediaServiceTests(TestCase):
    """Test MediaService utility functions"""

    def setUp(self):
        """Create test user"""
        self.user = CustomUser.objects.create_user(
            username='media_test_user',
            email='media@test.com',
            password='TestPass123!',
            role='student'
        )

    def test_create_media_record_from_uploaded_file(self):
        """Test creating SystemMedia from uploaded file"""
        test_file = SimpleUploadedFile(
            name='test.txt',
            content=b'test content',
            content_type='text/plain'
        )

        media = MediaService.create_media_record(
            file_obj=test_file,
            uploaded_by=self.user,
            purpose='general',
            description='Test file'
        )

        self.assertIsNotNone(media.id)
        self.assertEqual(media.filename, 'test.txt')
        self.assertEqual(media.file_type, 'document')
        self.assertEqual(media.uploaded_by, self.user)
        print("✓ Create media record: SUCCESS")

    def test_file_type_detection_pdf(self):
        """Test MIME type detection for PDF"""
        test_file = SimpleUploadedFile(
            name='document.pdf',
            content=b'%PDF-1.4',
            content_type='application/pdf'
        )

        media = MediaService.create_media_record(
            file_obj=test_file,
            uploaded_by=self.user,
            purpose='submission'
        )

        self.assertEqual(media.file_type, 'document')
        self.assertEqual(media.mime_type, 'application/pdf')
        print("✓ PDF detection: SUCCESS")

    def test_file_type_detection_image(self):
        """Test MIME type detection for image"""
        test_file = SimpleUploadedFile(
            name='image.png',
            content=b'PNG',
            content_type='image/png'
        )

        media = MediaService.create_media_record(
            file_obj=test_file,
            uploaded_by=self.user,
            purpose='general'
        )

        self.assertEqual(media.file_type, 'image')
        print("✓ Image detection: SUCCESS")

    def test_get_file_type_from_mime(self):
        """Test file type determination from MIME type"""
        file_types = {
            'application/pdf': 'document',
            'image/jpeg': 'image',
            'audio/mpeg': 'audio',
            'video/mp4': 'video',
            'application/zip': 'archive',
        }

        for mime_type, expected_type in file_types.items():
            result = MediaService.get_file_type(mime_type)
            self.assertEqual(result, expected_type)

        print("✓ File type detection from MIME: SUCCESS")

    def test_guess_mime_type(self):
        """Test MIME type guessing from filename"""
        mime_tests = {
            'file.pdf': 'application/pdf',
            'image.jpg': 'image/jpeg',
            'video.mp4': 'video/mp4',
            'archive.zip': 'application/zip',
        }

        for filename, expected_mime in mime_tests.items():
            mime = MediaService.guess_mime_type(filename)
            self.assertIsNotNone(mime)
            print(f"  {filename} -> {mime}")

        print("✓ MIME type guessing: SUCCESS")


class SystemMediaModelTests(TestCase):
    """Test SystemMedia model functionality"""

    def setUp(self):
        """Create test user and submission"""
        self.user = CustomUser.objects.create_user(
            username='model_test_user',
            email='model@test.com',
            password='TestPass123!',
            role='student'
        )

        supervisor = CustomUser.objects.create_user(
            username='supervisor_model_test',
            email='supervisor@test.com',
            password='TestPass123!',
            role='supervisor'
        )
        SupervisorProfile.objects.create(user=supervisor)

        StudentProfile.objects.create(user=self.user, supervisor=supervisor)

        self.submission = Submission.objects.create(
            student=self.user,
            title='Test Submission',
            document_type='thesis',
            version_number=1
        )

    def test_systemmedia_with_generic_relation(self):
        """Test SystemMedia with GenericForeignKey relationship"""
        media = SystemMedia.objects.create(
            filename='submission.pdf',
            file_type='document',
            mime_type='application/pdf',
            file_size=5120,
            uploaded_by=self.user,
            purpose='submission'
        )

        # Add generic relationship
        content_type = ContentType.objects.get_for_model(Submission)
        media.content_type = content_type
        media.object_id = self.submission.pk
        media.save()

        # Retrieve and verify
        self.assertEqual(media.content_object, self.submission)
        self.assertEqual(media.related_model_name, 'submission')
        print("✓ GenericForeignKey relationship: SUCCESS")

    def test_systemmedia_purpose_choices(self):
        """Test all purpose choices are available"""
        purposes = [
            'submission',
            'feedback',
            'template',
            'manuscript',
            'progress_update',
            'general'
        ]

        for purpose in purposes:
            media = SystemMedia.objects.create(
                filename=f'{purpose}.pdf',
                file_type='document',
                uploaded_by=self.user,
                purpose=purpose
            )
            self.assertEqual(media.purpose, purpose)

        print("✓ All purpose choices work: SUCCESS")

    def test_systemmedia_soft_delete(self):
        """Test soft delete functionality"""
        from django.utils import timezone

        media = SystemMedia.objects.create(
            filename='delete_test.pdf',
            file_type='document',
            uploaded_by=self.user,
            purpose='general',
            is_active=True
        )

        self.assertIsNone(media.deleted_at)
        self.assertTrue(media.is_active)

        # Soft delete
        from adminpanel.media_service import MediaService
        MediaService.soft_delete_media(media.id)

        media.refresh_from_db()
        self.assertIsNotNone(media.deleted_at)
        self.assertFalse(media.is_active)
        print("✓ Soft delete: SUCCESS")

    def test_systemmedia_file_size_display(self):
        """Test file size formatting"""
        test_cases = [
            (512, 'B'),
            (1024, 'KB'),
            (1048576, 'MB'),
            (1073741824, 'GB'),
        ]

        for size, unit in test_cases:
            media = SystemMedia.objects.create(
                filename='size_test.pdf',
                file_type='document',
                file_size=size,
                uploaded_by=self.user
            )
            display = media.get_file_size_display()
            self.assertIn(unit, display)

        print("✓ File size display formatting: SUCCESS")


class SubmissionMediaIntegrationTests(TestCase):
    """Test SystemMedia integration with Submission model"""

    def setUp(self):
        """Create test data"""
        self.user = CustomUser.objects.create_user(
            username='submit_test_user',
            email='submit@test.com',
            password='TestPass123!',
            role='student'
        )

        supervisor = CustomUser.objects.create_user(
            username='submit_supervisor',
            email='submit_supervisor@test.com',
            password='TestPass123!',
            role='supervisor'
        )
        SupervisorProfile.objects.create(user=supervisor)

        StudentProfile.objects.create(user=self.user, supervisor=supervisor)

    def test_submission_with_systemmedia(self):
        """Test Submission linked to SystemMedia"""
        submission = Submission.objects.create(
            student=self.user,
            title='Research Paper',
            document_type='thesis',
            version_number=1
        )

        # Create SystemMedia for submission
        media = SystemMedia.objects.create(
            filename='research_paper.pdf',
            file_type='document',
            file_size=10240,
            uploaded_by=self.user,
            purpose='submission'
        )

        # Link to submission
        content_type = ContentType.objects.get_for_model(Submission)
        media.content_type = content_type
        media.object_id = submission.pk
        media.save()

        # Query back
        related_media = SystemMedia.objects.filter(
            content_type=content_type,
            object_id=submission.pk,
            purpose='submission'
        )

        self.assertEqual(related_media.count(), 1)
        self.assertEqual(related_media.first().filename, 'research_paper.pdf')
        print("✓ Submission SystemMedia linking: SUCCESS")


class TemplateMediaIntegrationTests(TestCase):
    """Test SystemMedia integration with Template model"""

    def setUp(self):
        """Create test user"""
        self.manager = CustomUser.objects.create_user(
            username='template_test_user',
            email='template@test.com',
            password='TestPass123!',
            role='manager'
        )

    def test_template_with_systemmedia(self):
        """Test Template linked to SystemMedia"""
        template = Template.objects.create(
            title='Thesis Template',
            description='Standard thesis template',
            category='Book',
            uploaded_by=self.manager
        )

        # Create SystemMedia for template
        media = SystemMedia.objects.create(
            filename='thesis_template.docx',
            file_type='document',
            file_size=102400,
            uploaded_by=self.manager,
            purpose='template'
        )

        # Link to template
        content_type = ContentType.objects.get_for_model(Template)
        media.content_type = content_type
        media.object_id = template.pk
        media.save()

        # Query back
        related_media = SystemMedia.objects.filter(
            content_type=content_type,
            object_id=template.pk,
            purpose='template'
        )

        self.assertEqual(related_media.count(), 1)
        print("✓ Template SystemMedia linking: SUCCESS")


class PaperMediaIntegrationTests(TestCase):
    """Test SystemMedia integration with Paper model"""

    def setUp(self):
        """Create test user"""
        self.manager = CustomUser.objects.create_user(
            username='paper_test_user',
            email='paper@test.com',
            password='TestPass123!',
            role='manager'
        )

    def test_paper_with_systemmedia(self):
        """Test Paper manuscript linked to SystemMedia"""
        paper = Paper.objects.create(
            title='Machine Learning Study',
            internal_external='external',
            paper_type='journal',
            status='draft',
            created_by=self.manager
        )

        # Create SystemMedia for manuscript
        media = SystemMedia.objects.create(
            filename='ml_study_v1.pdf',
            file_type='document',
            file_size=204800,
            uploaded_by=self.manager,
            purpose='manuscript'
        )

        # Link to paper
        content_type = ContentType.objects.get_for_model(Paper)
        media.content_type = content_type
        media.object_id = paper.pk
        media.save()

        # Query back
        related_media = SystemMedia.objects.filter(
            content_type=content_type,
            object_id=paper.pk,
            purpose='manuscript'
        )

        self.assertEqual(related_media.count(), 1)
        print("✓ Paper SystemMedia linking: SUCCESS")


class SystemMediaQueryTests(TestCase):
    """Test SystemMedia query optimization"""

    def setUp(self):
        """Create multiple test records"""
        self.user1 = CustomUser.objects.create_user(
            username='query_user1',
            password='TestPass123!',
            role='student'
        )

        self.user2 = CustomUser.objects.create_user(
            username='query_user2',
            password='TestPass123!',
            role='student'
        )

        # Create multiple media records
        for i in range(5):
            SystemMedia.objects.create(
                filename=f'file_{i}.pdf',
                file_type='document',
                uploaded_by=self.user1,
                purpose='submission'
            )

        for i in range(3):
            SystemMedia.objects.create(
                filename=f'template_{i}.docx',
                file_type='document',
                uploaded_by=self.user2,
                purpose='template'
            )

    def test_filter_by_uploader(self):
        """Test filtering media by uploader"""
        user1_media = SystemMedia.objects.filter(uploaded_by=self.user1)
        self.assertEqual(user1_media.count(), 5)

        user2_media = SystemMedia.objects.filter(uploaded_by=self.user2)
        self.assertEqual(user2_media.count(), 3)

        print("✓ Filter by uploader: SUCCESS")

    def test_filter_by_purpose(self):
        """Test filtering media by purpose"""
        submissions = SystemMedia.objects.filter(purpose='submission')
        self.assertEqual(submissions.count(), 5)

        templates = SystemMedia.objects.filter(purpose='template')
        self.assertEqual(templates.count(), 3)

        print("✓ Filter by purpose: SUCCESS")

    def test_filter_by_file_type(self):
        """Test filtering media by file type"""
        documents = SystemMedia.objects.filter(file_type='document')
        self.assertEqual(documents.count(), 8)

        print("✓ Filter by file type: SUCCESS")

    def test_ordering(self):
        """Test media ordering by upload date"""
        media_list = list(SystemMedia.objects.all().order_by('-uploaded_at'))
        self.assertEqual(len(media_list), 8)

        print("✓ Ordering by date: SUCCESS")


if __name__ == '__main__':
    import unittest

    print("\n" + "="*70)
    print("SYSTEMMEDIA INTEGRATION TEST SUITE")
    print("="*70 + "\n")

    # Load and run tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(MediaServiceTests))
    suite.addTests(loader.loadTestsFromTestCase(SystemMediaModelTests))
    suite.addTests(loader.loadTestsFromTestCase(SubmissionMediaIntegrationTests))
    suite.addTests(loader.loadTestsFromTestCase(TemplateMediaIntegrationTests))
    suite.addTests(loader.loadTestsFromTestCase(PaperMediaIntegrationTests))
    suite.addTests(loader.loadTestsFromTestCase(SystemMediaQueryTests))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "="*70)
    print(f"SUMMARY")
    print("="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    if result.wasSuccessful():
        print("✓ ALL TESTS PASSED")
    else:
        print("✗ SOME TESTS FAILED")
    print("="*70 + "\n")

    sys.exit(0 if result.wasSuccessful() else 1)
