"""
Dual-Write Media System Test
Tests filesystem + database backup functionality
Run with: python manage.py test dualwrite_media_test
"""

import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_manage.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from adminpanel.media_models import SystemMedia
from adminpanel.media_service import MediaService

CustomUser = get_user_model()


class DualWriteMediaTests(TestCase):
    """Test filesystem + database dual-write functionality"""

    def setUp(self):
        """Create test user"""
        self.user = CustomUser.objects.create_user(
            username='dualwrite_test_user',
            email='dualwrite@test.com',
            password='TestPass123!',
            role='student'
        )

    def test_create_media_with_dual_write(self):
        """Test creating media with database backup"""
        test_file = SimpleUploadedFile(
            name='dualwrite_test.pdf',
            content=b'%PDF-1.4 Test PDF Content',
            content_type='application/pdf'
        )

        media = MediaService.create_media_record_with_backup(
            file_obj=test_file,
            uploaded_by=self.user,
            purpose='submission',
            backup_to_db=True
        )

        # Verify filesystem write
        self.assertTrue(media.file)
        self.assertTrue(os.path.exists(media.file.path))

        # Verify database write
        self.assertTrue(media.stored_in_db)
        self.assertIsNotNone(media.file_blob)
        self.assertGreater(len(media.file_blob), 0)

        # Verify content matches
        with open(media.file.path, 'rb') as f:
            fs_content = f.read()
        
        self.assertEqual(fs_content, media.file_blob)
        print("✓ Dual-write creation: SUCCESS")

    def test_get_file_from_database(self):
        """Test retrieving file from database backup"""
        test_content = b'Database backup test content'
        test_file = SimpleUploadedFile(
            name='db_retrieval_test.txt',
            content=test_content,
            content_type='text/plain'
        )

        media = MediaService.create_media_record_with_backup(
            file_obj=test_file,
            uploaded_by=self.user,
            purpose='general',
            backup_to_db=True
        )

        # Retrieve from database
        retrieved_blob = MediaService.get_file_from_db(media.id)
        
        self.assertIsNotNone(retrieved_blob)
        self.assertEqual(retrieved_blob, test_content)
        print("✓ Database file retrieval: SUCCESS")

    def test_restore_from_database_to_filesystem(self):
        """Test restoring file from database to filesystem"""
        test_content = b'Recovery test content'
        test_file = SimpleUploadedFile(
            name='recovery_test.txt',
            content=test_content,
            content_type='text/plain'
        )

        media = MediaService.create_media_record_with_backup(
            file_obj=test_file,
            uploaded_by=self.user,
            purpose='general',
            backup_to_db=True
        )

        # Delete filesystem file
        file_path = media.file.path
        if os.path.exists(file_path):
            os.remove(file_path)
        
        self.assertFalse(os.path.exists(file_path))

        # Restore from database
        result = MediaService.restore_file_from_db_to_filesystem(media.id)
        
        self.assertTrue(result)
        self.assertTrue(os.path.exists(file_path))

        # Verify restored content matches
        with open(file_path, 'rb') as f:
            restored_content = f.read()
        
        self.assertEqual(restored_content, test_content)
        print("✓ File recovery from database: SUCCESS")

    def test_dual_write_without_backup(self):
        """Test creating media without database backup"""
        test_file = SimpleUploadedFile(
            name='filesystem_only.txt',
            content=b'Filesystem only content',
            content_type='text/plain'
        )

        media = MediaService.create_media_record_with_backup(
            file_obj=test_file,
            uploaded_by=self.user,
            purpose='general',
            backup_to_db=False
        )

        # Verify filesystem write
        self.assertTrue(media.file)
        self.assertTrue(os.path.exists(media.file.path))

        # Verify NO database write
        self.assertFalse(media.stored_in_db)
        self.assertIsNone(media.file_blob)
        print("✓ Filesystem-only mode: SUCCESS")

    def test_file_blob_is_independent_copy(self):
        """Test that file_blob is independent of file field"""
        test_content = b'Original content'
        test_file = SimpleUploadedFile(
            name='independent_copy_test.txt',
            content=test_content,
            content_type='text/plain'
        )

        media = MediaService.create_media_record_with_backup(
            file_obj=test_file,
            uploaded_by=self.user,
            purpose='general',
            backup_to_db=True
        )

        # Verify both exist independently
        self.assertIsNotNone(media.file)
        self.assertIsNotNone(media.file_blob)

        # Verify they contain the same data
        with open(media.file.path, 'rb') as f:
            fs_content = f.read()
        
        self.assertEqual(fs_content, media.file_blob)
        self.assertEqual(len(media.file_blob), len(fs_content))
        print("✓ Independent file copies: SUCCESS")


if __name__ == '__main__':
    import unittest

    print("\n" + "="*70)
    print("DUAL-WRITE MEDIA SYSTEM TEST")
    print("="*70 + "\n")

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    suite.addTests(loader.loadTestsFromTestCase(DualWriteMediaTests))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    print("\n" + "="*70)
    print(f"Tests run: {result.testsRun}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    if result.wasSuccessful():
        print("✓ ALL DUAL-WRITE TESTS PASSED")
    else:
        print("✗ SOME TESTS FAILED")
    print("="*70 + "\n")

    sys.exit(0 if result.wasSuccessful() else 1)
