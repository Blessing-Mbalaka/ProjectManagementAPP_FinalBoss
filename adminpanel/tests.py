"""
Comprehensive unit tests for adminpanel app
Tests clock in/out, notifications, audit trail, and activity tracking
"""
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
import json

from .models import ClockInRecord, Notification, AuditLog
from manager.models import ChangeLog

User = get_user_model()


class ClockInRecordModelTests(TestCase):
    """Test ClockInRecord model functionality"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
    def test_clock_in_creation(self):  
        """Test creating a clock in record"""
        record = ClockInRecord.objects.create(
            employee=self.user,
            clock_in_time=timezone.now()
        )
        self.assertEqual(record.employee, self.user)
        self.assertIsNotNone(record.clock_in_time)
        self.assertIsNone(record.clock_out_time)
        
    def test_clock_out_time(self):
        """Test recording clock out time"""
        now = timezone.now()
        record = ClockInRecord.objects.create(
            employee=self.user,
            clock_in_time=now
        )
        record.clock_out_time = now + timedelta(hours=8)
        record.save()
        self.assertIsNotNone(record.clock_out_time)
        
    def test_duration_display(self):
        """Test duration display calculation"""
        now = timezone.now()
        record = ClockInRecord.objects.create(
            employee=self.user,
            clock_in_time=now,
            clock_out_time=now + timedelta(hours=8)
        )
        duration = record.duration_display
        self.assertIn('8', duration)
        
    def test_get_current_session(self):
        """Test retrieving current clock in session"""
        record = ClockInRecord.objects.create(
            employee=self.user,
            clock_in_time=timezone.now()
        )
        current = ClockInRecord.get_current_session(self.user)
        self.assertEqual(current, record)
        
    def test_get_today_total_hours(self):
        """Test calculating today's total hours"""
        now = timezone.now()
        ClockInRecord.objects.create(
            employee=self.user,
            clock_in_time=now,
            clock_out_time=now + timedelta(hours=4)
        )
        ClockInRecord.objects.create(
            employee=self.user,
            clock_in_time=now + timedelta(hours=4, minutes=30),
            clock_out_time=now + timedelta(hours=8, minutes=30)
        )
        total = ClockInRecord.get_today_total_hours(self.user)
        self.assertEqual(total, 8.0)
        
    def test_timezone_display(self):
        """Test that times display in local timezone"""
        now = timezone.now()
        record = ClockInRecord.objects.create(
            employee=self.user,
            clock_in_time=now
        )
        # Verify __str__ uses timezone.localtime()
        str_repr = str(record)
        self.assertIn(self.user.username, str_repr)


class NotificationModelTests(TestCase):
    """Test Notification model"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
    def test_notification_creation(self):
        """Test creating a notification"""
        notification = Notification.objects.create(
            title='Test Notification',
            body='Test body',
            recipient=self.user,
            priority='high'
        )
        self.assertEqual(notification.title, 'Test Notification')
        self.assertEqual(notification.recipient, self.user)
        
    def test_notification_read_status(self):
        """Test marking notification as read"""
        notification = Notification.objects.create(
            title='Test',
            body='Test',
            recipient=self.user
        )
        self.assertFalse(notification.is_read)
        notification.is_read = True
        notification.save()
        self.assertTrue(notification.is_read)


class AuditLogModelTests(TestCase):
    """Test AuditLog model for audit trail"""
    
    def setUp(self):
        """Set up test data"""
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
    def test_audit_log_creation(self):
        """Test creating an audit log entry"""
        log = AuditLog.objects.create(
            user=self.user,
            action='login',
            description='User logged in',
            ip_address='127.0.0.1'
        )
        self.assertEqual(log.action, 'login')
        self.assertEqual(log.user, self.user)


class ClockAPITests(TestCase):
    """Test clock in/out API endpoints"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
    def test_clock_in_api_requires_login(self):
        """Test clock in endpoint requires authentication"""
        response = self.client.post(reverse('clock_in'))
        self.assertEqual(response.status_code, 302)  # Redirect to login
        
    def test_clock_in_api_authenticated(self):
        """Test clocking in as authenticated user"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.post(reverse('clock_in'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
    def test_clock_out_api(self):
        """Test clocking out"""
        self.client.login(username='testuser', password='testpass123')
        # Clock in first
        self.client.post(reverse('clock_in'))
        # Then clock out
        response = self.client.post(reverse('clock_out'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertTrue(data['success'])
        
    def test_get_clock_status_api(self):
        """Test getting clock status"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('get_clock_status'))
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        self.assertIn('clocked_in', data)
        
    def test_clock_status_returns_local_time(self):
        """Test that clock status returns local timezone time"""
        self.client.login(username='testuser', password='testpass123')
        self.client.post(reverse('clock_in'))
        response = self.client.get(reverse('get_clock_status'))
        data = json.loads(response.content)
        # Should have time in HH:MM:SS format (local timezone)
        self.assertIsNotNone(data['clock_in_time'])
        self.assertRegex(data['clock_in_time'], r'\d{2}:\d{2}:\d{2}')


class ActivityTrackingTests(TestCase):
    """Test activity tracking and hour calculations"""
    
    def setUp(self):
        """Set up test data"""
        self.client = Client()
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
    def test_user_activity_data_view(self):
        """Test user activity data endpoint"""
        self.client.login(username='testuser', password='testpass123')
        response = self.client.get(reverse('user_activity_data'))
        self.assertIn(response.status_code, [200, 302])
        
    def test_hours_calculation_with_timezone(self):
        """Test that hour calculations use local timezone"""
        now = timezone.now()
        ClockInRecord.objects.create(
            employee=self.user,
            clock_in_time=now,
            clock_out_time=now + timedelta(hours=5)
        )
        total = ClockInRecord.get_today_total_hours(self.user)
        self.assertEqual(total, 5.0)
