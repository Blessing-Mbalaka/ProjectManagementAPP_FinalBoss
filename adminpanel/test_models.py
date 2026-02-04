"""
Simplified test suite for adminpanel app models
Tests focus on model instantiation and basic operations
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from .models import ClockInRecord, Notification, AuditLog
from manager.models import ChangeLog

User = get_user_model()


class ClockInRecordModelTests(TestCase):
    """Test the ClockInRecord model"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='employee', password='test123')
    
    def test_clock_in_record_creation(self):
        """Test creating a clock in record"""
        from django.utils import timezone
        record = ClockInRecord.objects.create(
            employee=self.user,
            clock_in_time=timezone.now()
        )
        self.assertIsNotNone(record.clock_in_time)
        self.assertEqual(record.employee, self.user)


class NotificationModelTests(TestCase):
    """Test the Notification model"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='user', password='test123')
    
    def test_notification_creation(self):
        """Test creating a notification"""
        notification = Notification.objects.create(
            title='Test Notification',
            body='Test body',
            priority='normal',
            audience='all'
        )
        self.assertEqual(notification.title, 'Test Notification')
        self.assertEqual(notification.audience, 'all')


class AuditLogModelTests(TestCase):
    """Test the AuditLog model"""
    
    def setUp(self):
        self.user = User.objects.create_user(username='user', password='test123')
    
    def test_audit_log_creation(self):
        """Test creating an audit log entry"""
        log = AuditLog.objects.create(
            action='create_cost_centre',
            entity_type='CostCentre',
            entity_id=1,
            entity_name='Test Centre',
            user=self.user
        )
        self.assertEqual(log.action, 'create_cost_centre')
        self.assertEqual(log.entity_type, 'CostCentre')
