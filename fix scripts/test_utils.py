"""
Test utilities and fixtures for Django test suite
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
import os

User = get_user_model()


class BaseTestCase(TestCase):
    """Base test case with common setup and utilities"""
    
    def setUp(self):
        """Set up common test data"""
        self.test_user = self.create_test_user()
        self.test_admin = self.create_test_user(username='admin', role='admin', is_staff=True)
        self.test_supervisor = self.create_test_user(username='supervisor', role='supervisor')
        
    def create_test_user(self, username='testuser', email=None, password='testpass123', 
                        role='employee', is_staff=False):
        """Create a test user with default values"""
        if email is None:
            email = f'{username}@example.com'
            
        return User.objects.create_user(
            username=username,
            email=email,
            password=password,
            role=role,
            is_staff=is_staff
        )
        
    def create_test_users(self, count=5):
        """Create multiple test users"""
        users = []
        for i in range(count):
            user = self.create_test_user(username=f'user{i}')
            users.append(user)
        return users
        
    def assert_login_required(self, client, url, method='get'):
        """Assert that a view requires login"""
        if method == 'get':
            response = client.get(url)
        else:
            response = client.post(url)
            
        self.assertEqual(response.status_code, 302)  # Redirect to login
        
    def assert_permission_denied(self, client, url, user=None, method='get'):
        """Assert that a view denies permission"""
        if user:
            client.login(username=user.username, password='testpass123')
            
        if method == 'get':
            response = client.get(url)
        else:
            response = client.post(url)
            
        self.assertEqual(response.status_code, 403)  # Forbidden


class MockEmailBackend:
    """Mock email backend for testing without SMTP"""
    
    @staticmethod
    def send_mail(subject, message, from_email, recipient_list, **kwargs):
        """Mock email sending"""
        return 1  # Simulate success
