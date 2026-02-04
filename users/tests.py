"""
Simplified test suite for users app
Tests focus on model instantiation and user creation
"""
from django.test import TestCase
from django.contrib.auth import get_user_model

User = get_user_model()


class CustomUserModelTests(TestCase):
    """Test the CustomUser model"""
    
    def test_user_creation(self):
        """Test creating a user"""
        user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            role='staff'
        )
        self.assertEqual(user.username, 'testuser')
        self.assertEqual(user.role, 'staff')
    
    def test_user_with_different_roles(self):
        """Test creating users with different roles"""
        admin = User.objects.create_user(username='admin', password='test', role='admin')
        supervisor = User.objects.create_user(username='supervisor', password='test', role='supervisor')
        manager = User.objects.create_user(username='manager', password='test', role='manager')
        staff = User.objects.create_user(username='staff', password='test', role='staff')
        
        self.assertEqual(admin.role, 'admin')
        self.assertEqual(supervisor.role, 'supervisor')
        self.assertEqual(manager.role, 'manager')
        self.assertEqual(staff.role, 'staff')


class UserAuthenticationTests(TestCase):
    """Test user authentication"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass123',
            role='staff'
        )
    
    def test_user_authentication(self):
        """Test authenticating a user"""
        from django.contrib.auth import authenticate
        authenticated_user = authenticate(username='testuser', password='testpass123')
        self.assertIsNotNone(authenticated_user)
        self.assertEqual(authenticated_user.username, 'testuser')
    
    def test_user_password_set(self):
        """Test that user password is properly hashed"""
        self.assertTrue(self.user.check_password('testpass123'))
        self.assertFalse(self.user.check_password('wrongpassword'))


class SuperuserCreationTests(TestCase):
    """Test superuser creation"""
    
    def test_superuser_creation(self):
        """Test creating a superuser"""
        superuser = User.objects.create_superuser(
            username='admin',
            password='admin123',
            email='admin@example.com'
        )
        self.assertEqual(superuser.username, 'admin')
        self.assertTrue(superuser.is_staff)
        self.assertTrue(superuser.is_superuser)
        self.assertEqual(superuser.role, 'admin')
