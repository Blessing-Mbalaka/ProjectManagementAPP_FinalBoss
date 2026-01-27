"""
Page Rendering Test Suite
Tests all major pages render correctly without errors.
Run with: python manage.py test page_rendering_test
Or directly: python page_rendering_test.py
"""

import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_manage.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from projects.models import Submission, StudentProfile
from manager.models import Template
from adminpanel.models import SupervisorProfile
from django.urls import reverse

CustomUser = get_user_model()


class PageRenderingTests(TestCase):
    """Test all major pages render without errors"""

    def setUp(self):
        """Create test users for page rendering tests"""
        self.client = Client()

        # Create test users
        self.admin_user = CustomUser.objects.create_user(
            username='admin_render_test',
            email='admin@render.test',
            password='TestPass123!',
            role='admin',
            is_staff=True,
            is_superuser=True
        )

        self.supervisor = CustomUser.objects.create_user(
            username='supervisor_render_test',
            email='supervisor@render.test',
            password='TestPass123!',
            role='supervisor'
        )
        SupervisorProfile.objects.create(user=self.supervisor)

        self.student = CustomUser.objects.create_user(
            username='student_render_test',
            email='student@render.test',
            password='TestPass123!',
            role='student'
        )
        StudentProfile.objects.create(
            user=self.student,
            supervisor=self.supervisor
        )

        self.manager = CustomUser.objects.create_user(
            username='manager_render_test',
            email='manager@render.test',
            password='TestPass123!',
            role='manager'
        )

    def test_login_page(self):
        """Test login page renders"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'users/login.html')
        print("✓ Login page renders: 200")

    def test_admin_overview(self):
        """Test admin overview page"""
        self.client.force_login(self.admin_user)
        response = self.client.get('/overview/')
        self.assertEqual(response.status_code, 200)
        print("✓ Admin overview: 200")

    def test_student_dashboard(self):
        """Test student dashboard page"""
        self.client.force_login(self.student)
        response = self.client.get('/projects/student_dashboard/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'student', response.content.lower())
        print("✓ Student dashboard: 200")

    def test_supervisor_portal_dashboard(self):
        """Test supervisor portal dashboard"""
        self.client.force_login(self.supervisor)
        response = self.client.get('/adminpanel/supervisor-portal/dashboard/')
        self.assertEqual(response.status_code, 200)
        print("✓ Supervisor portal dashboard: 200")

    def test_supervisor_portal_messages(self):
        """Test supervisor messages page"""
        self.client.force_login(self.supervisor)
        response = self.client.get('/adminpanel/supervisor-portal/messages/')
        self.assertEqual(response.status_code, 200)
        print("✓ Supervisor messages: 200")

    def test_admin_systemmedia_page(self):
        """Test SystemMedia admin page"""
        self.client.force_login(self.admin_user)
        response = self.client.get('/admin/adminpanel/systemmedia/')
        self.assertEqual(response.status_code, 200)
        print("✓ SystemMedia admin: 200")

    def test_404_handling(self):
        """Test 404 error page renders"""
        self.client.force_login(self.admin_user)
        response = self.client.get('/nonexistent-page-12345/')
        self.assertEqual(response.status_code, 404)
        print("✓ 404 error page: 404")

    def test_student_can_access_student_dashboard(self):
        """Test student role access control"""
        self.client.force_login(self.student)
        response = self.client.get('/projects/student_dashboard/')
        self.assertEqual(response.status_code, 200)
        print("✓ Student access control: PASSED")

    def test_supervisor_cannot_access_admin_overview(self):
        """Test supervisor cannot access admin pages"""
        self.client.force_login(self.supervisor)
        response = self.client.get('/overview/')
        self.assertNotEqual(response.status_code, 200)
        print(f"✓ Supervisor admin access denied: {response.status_code}")


class ViewImportTests(TestCase):
    """Test that all view modules import without errors"""

    def test_projects_views_imports(self):
        """Test projects views module"""
        try:
            from projects import views
            self.assertTrue(hasattr(views, 'submit_document'))
            self.assertTrue(hasattr(views, 'send_chat_message'))
            self.assertTrue(hasattr(views, 'student_dashboard'))
            print("✓ Projects views import: SUCCESS")
        except ImportError as e:
            self.fail(f"Failed to import projects.views: {str(e)}")

    def test_adminpanel_views_imports(self):
        """Test adminpanel views module"""
        try:
            from adminpanel import views
            self.assertTrue(hasattr(views, 'provide_feedback'))
            self.assertTrue(hasattr(views, 'supervisor_dashboard'))
            print("✓ Adminpanel views import: SUCCESS")
        except ImportError as e:
            self.fail(f"Failed to import adminpanel.views: {str(e)}")

    def test_manager_views_imports(self):
        """Test manager views module"""
        try:
            from manager import views
            self.assertTrue(hasattr(views, 'add_template'))
            print("✓ Manager views import: SUCCESS")
        except ImportError as e:
            self.fail(f"Failed to import manager.views: {str(e)}")

    def test_media_service_imports(self):
        """Test MediaService utility"""
        try:
            from adminpanel.media_service import MediaService
            self.assertTrue(hasattr(MediaService, 'create_media_record'))
            self.assertTrue(hasattr(MediaService, 'link_existing_file'))
            print("✓ MediaService import: SUCCESS")
        except ImportError as e:
            self.fail(f"Failed to import MediaService: {str(e)}")

    def test_systemmedia_model_imports(self):
        """Test SystemMedia model"""
        try:
            from adminpanel.media_models import SystemMedia
            self.assertTrue(hasattr(SystemMedia, 'get_file_size_display'))
            print("✓ SystemMedia model import: SUCCESS")
        except ImportError as e:
            self.fail(f"Failed to import SystemMedia: {str(e)}")


class ModelTests(TestCase):
    """Test model functionality after changes"""

    def setUp(self):
        """Create test user"""
        self.user = CustomUser.objects.create_user(
            username='model_test_user',
            email='model@test.com',
            password='TestPass123!',
            role='student'
        )

    def test_systemmedia_model_creation(self):
        """Test SystemMedia model can be instantiated"""
        from adminpanel.media_models import SystemMedia

        media = SystemMedia.objects.create(
            filename='test.pdf',
            file_type='document',
            mime_type='application/pdf',
            file_size=2048,
            uploaded_by=self.user,
            purpose='submission'
        )

        self.assertEqual(media.filename, 'test.pdf')
        self.assertEqual(media.file_type, 'document')
        self.assertEqual(media.uploaded_by, self.user)
        self.assertEqual(media.purpose, 'submission')
        print("✓ SystemMedia model creation: SUCCESS")

    def test_systemmedia_file_size_display(self):
        """Test file size display formatting"""
        from adminpanel.media_models import SystemMedia

        media = SystemMedia.objects.create(
            filename='large.pdf',
            file_type='document',
            file_size=1048576,  # 1 MB
            uploaded_by=self.user,
            purpose='feedback'
        )

        display = media.get_file_size_display()
        self.assertIn('MB', display)
        print(f"✓ File size display: {display}")

    def test_systemmedia_uploader_name(self):
        """Test uploader name property"""
        from adminpanel.media_models import SystemMedia

        media = SystemMedia.objects.create(
            filename='test.doc',
            file_type='document',
            uploaded_by=self.user,
            purpose='general'
        )

        self.assertEqual(media.uploader_name, self.user.username)
        print(f"✓ Uploader name property: {media.uploader_name}")


if __name__ == '__main__':
    import unittest

    print("\n" + "="*70)
    print("PAGE RENDERING TEST SUITE")
    print("="*70 + "\n")

    # Load and run tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    suite.addTests(loader.loadTestsFromTestCase(PageRenderingTests))
    suite.addTests(loader.loadTestsFromTestCase(ViewImportTests))
    suite.addTests(loader.loadTestsFromTestCase(ModelTests))

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
