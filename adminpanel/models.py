from django.conf import settings
from django.db import models
from django.apps import apps
from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError


class CostCentre(models.Model):
    name = models.CharField(max_length=100, unique=True)
    total_received = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    def __str__(self):
        return self.name

    @property
    def total_remaining(self):
        try:
            received = self.get_total_received()
            spent = Decimal(str(self.total_spent)) if self.total_spent else Decimal('0.00')
            return received - spent
        except (InvalidOperation, TypeError):
            return Decimal('0.00')
    
    def get_total_received(self):
        """Calculate total received from sum of all payments"""
        try:
            total = self.payments.aggregate(total=models.Sum('amount'))['total']
            if total is None:
                return Decimal('0.00')
            return Decimal(str(total))
        except (InvalidOperation, TypeError):
            return Decimal('0.00')
    
    def payment_count(self):
        """Get number of payments received"""
        return self.payments.count()


class CostCentrePayment(models.Model):
    """Track incremental payments received for a cost centre"""
    cost_centre = models.ForeignKey(CostCentre, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=255, blank=True, help_text="e.g., Project Name, Phase 1")
    payment_date = models.DateField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-payment_date', '-created_at']
    
    def __str__(self):
        return f"{self.cost_centre.name} - R {self.amount} ({self.payment_date})"
    
    def save(self, *args, **kwargs):
        try:
            # Validate decimal places
            self.amount = Decimal(str(self.amount))
            if self.amount.as_tuple().exponent < -2:
                raise ValidationError('Amount must have at most 2 decimal places')
        except (InvalidOperation, ValueError, TypeError) as e:
            raise ValidationError(f'Invalid amount: {e}')
        
        super().save(*args, **kwargs)
        
        # Update cost centre's total_received by summing all payments
        try:
            total = CostCentrePayment.objects.filter(cost_centre=self.cost_centre).aggregate(
                total=models.Sum('amount')
            )['total'] or Decimal('0.00')
            self.cost_centre.total_received = Decimal(str(total))
            self.cost_centre.save(update_fields=['total_received'])
        except (InvalidOperation, Exception) as e:
            # Log but don't fail
            pass


class Expenditure(models.Model):
    EXPENSE_CATEGORY_CHOICES = [
        ('Salary', 'Salary'),
        ('Bursaries', 'Bursaries'),
        ('Invoices', 'Invoices'),
        ('Fitness', 'Fitness'),
        ('Equipment', 'Equipment/Office Resources'),
        ('Travel', 'Travel'),
    ]

    cost_centre = models.ForeignKey(CostCentre, on_delete=models.CASCADE, related_name='expenditures')
    month = models.CharField(max_length=20)
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50, choices=EXPENSE_CATEGORY_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    closing_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    oracle_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    def save(self, *args, **kwargs):
        try:
            # Convert to Decimal with error handling
            self.amount = Decimal(str(self.amount))
            self.opening_balance = Decimal(str(self.opening_balance))
            
            # Validate decimal places
            if self.amount.as_tuple().exponent < -2:
                raise ValidationError('Amount must have at most 2 decimal places')
            if self.opening_balance.as_tuple().exponent < -2:
                raise ValidationError('Opening balance must have at most 2 decimal places')
            
            # Calculate closing balance with error handling
            try:
                self.closing_balance = self.opening_balance - self.amount
            except InvalidOperation:
                raise ValidationError('Error calculating closing balance: invalid number values')
                
        except InvalidOperation as e:
            raise ValidationError(f'Invalid decimal value: {e}')
        except (ValueError, TypeError) as e:
            raise ValidationError(f'Invalid number format: {e}')
        
        super().save(*args, **kwargs)

        # Update CostCentre total_spent with error handling
        try:
            total = Expenditure.objects.filter(cost_centre=self.cost_centre).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
            self.cost_centre.total_spent = Decimal(str(total))
            self.cost_centre.save()
        except InvalidOperation:
            # Log error but don't fail the save
            pass


    def __str__(self):
        return f"{self.name} ({self.category}) - {self.month}"
        

class SupervisorProfile(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, limit_choices_to={'role': 'admin'})
    department = models.CharField(max_length=100, blank=True, null=True)
    office_location = models.CharField(max_length=255, blank=True, null=True)
    title = models.CharField(max_length=50, default='Dr.')

    def __str__(self):
        return f"{self.title} {self.user.get_full_name()}"
    
class SupervisorFeedback(models.Model):
    submission = models.ForeignKey(
        'projects.Submission',  # ✅ Lazy reference by app_label.ModelName
        on_delete=models.CASCADE,
        related_name='supervisor_feedback'
    )
    supervisor = models.ForeignKey('adminpanel.SupervisorProfile', on_delete=models.CASCADE)
    comments = models.TextField()
    uploaded_file = models.FileField(upload_to='feedback_docs/', blank=True, null=True)
    status = models.CharField(max_length=30)  # We'll dynamically validate this in save()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Feedback by {self.supervisor.user.get_full_name()} on {self.submission.title}"

    def clean(self):
        # Validate status choices against Submission.STATUS_CHOICES
        Submission = apps.get_model('projects', 'Submission')
        valid_statuses = [choice[0] for choice in Submission.STATUS_CHOICES]
        if self.status not in valid_statuses:
            raise ValidationError(f"Invalid status: {self.status}. Must be one of: {valid_statuses}")


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_supervisor_profile(sender, instance, created, **kwargs):
    if created and instance.role in ['admin']:
        SupervisorProfile.objects.get_or_create(user=instance)



class Notification(models.Model):
    PRIORITY_CHOICES = [
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    AUDIENCE_CHOICES = [
        ('all', 'All Users'),
        ('role', 'By Role'),
        ('specific', 'Specific Users'),
    ]

    title = models.CharField(max_length=200)
    body = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')

    audience = models.CharField(max_length=10, choices=AUDIENCE_CHOICES, default='all')
    # If audience == 'role', store the role key (e.g., 'manager', 'staff', 'student')
    audience_role = models.CharField(max_length=20, blank=True, null=True)

    # If audience == 'specific', pick explicit users
    recipients = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='notifications_received'
    )

    is_pinned = models.BooleanField(default=False)
    send_email = models.BooleanField(default=False)  # for later delivery handling

    scheduled_at = models.DateTimeField(blank=True, null=True)
    expires_at = models.DateTimeField(blank=True, null=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='notifications_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.get_priority_display()})"

    def clean(self):
        if self.audience == 'role' and not self.audience_role:
            raise ValidationError("Please choose a role for the audience.")
        if self.audience == 'specific' and self.pk is None:
            # when creating, recipients will be saved after instance exists (save_m2m),
            # but we can still hint via form validation; leave model-level minimal.
            pass
"""Clock In/Out Model - Tracks employee attendance"""
from django.db import models
from users.models import CustomUser
from datetime import timedelta

class ClockInRecord(models.Model):
    """Records employee clock in/out times"""
    
    STATUS_CHOICES = [
        ('clocked_in', 'Clocked In'),
        ('clocked_out', 'Clocked Out'),
    ]
    
    employee = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='clock_records'
    )
    
    clock_in_time = models.DateTimeField(auto_now_add=True)
    clock_out_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='clocked_in')
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-clock_in_time']
        indexes = [
            models.Index(fields=['employee', '-clock_in_time']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.employee.username} - {self.clock_in_time.strftime('%Y-%m-%d %H:%M')}"
    
    @property
    def duration(self):
        """Calculate duration between clock in and out"""
        if self.clock_out_time:
            return self.clock_out_time - self.clock_in_time
        from django.utils import timezone
        return timezone.now() - self.clock_in_time
    
    @property
    def duration_display(self):
        """Return formatted duration string"""
        if not self.duration:
            return "0h 0m"
        total_seconds = int(self.duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours}h {minutes}m"
    
    @property
    def clock_out_time_display(self):
        if self.clock_out_time:
            return self.clock_out_time.strftime('%H:%M:%S')
        return "Still clocked in"
    
    def save(self, *args, **kwargs):
        if self.clock_out_time:
            self.status = 'clocked_out'
        else:
            self.status = 'clocked_in'
        super().save(*args, **kwargs)
    
    @classmethod
    def get_current_session(cls, employee):
        """Get current active clock in session"""
        return cls.objects.filter(employee=employee, clock_out_time__isnull=True).first()
    
    @classmethod
    def get_today_sessions(cls, employee):
        """Get all clock sessions for today"""
        from django.utils import timezone
        today = timezone.now().date()
        return cls.objects.filter(employee=employee, clock_in_time__date=today)
    
    @classmethod
    def get_today_total_hours(cls, employee):
        """Calculate total hours worked today"""
        sessions = cls.get_today_sessions(employee)
        total_duration = timedelta()
        for session in sessions:
            total_duration += session.duration
        total_seconds = int(total_duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        return f"{hours}h {minutes}m"