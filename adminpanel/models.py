from django.conf import settings
from django.db import models
from django.apps import apps
from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta


class ResearchCentre(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class CostCentre(models.Model):
    research_centre = models.ForeignKey(
        ResearchCentre,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cost_centres',
        help_text="Research centre this financial cost centre belongs to."
    )
    code = models.CharField(max_length=20, unique=True, help_text="University-assigned cost centre code")
    name = models.CharField(max_length=100, unique=True)
    client_name = models.CharField(max_length=150, blank=True, help_text="Client or stakeholder name linked to this cost centre")
    company_name = models.CharField(max_length=200, blank=True, help_text="Registered company or organisation name")
    company_registration_number = models.CharField(max_length=80, blank=True, help_text="CIPC or company registration number")
    vat_number = models.CharField(max_length=80, blank=True)
    industry = models.CharField(max_length=120, blank=True)
    company_website = models.URLField(blank=True)
    company_email = models.EmailField(blank=True)
    company_phone = models.CharField(max_length=50, blank=True)
    company_address = models.TextField(blank=True)
    contact_person_name = models.CharField(max_length=150, blank=True)
    contact_person_role = models.CharField(max_length=120, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=50, blank=True)
    crm_notes = models.TextField(blank=True)
    total_received = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    moa_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, null=True, blank=True, help_text="Memorandum of Understanding - Total expected/budgeted amount")
    phase_1_due_date = models.DateField(null=True, blank=True, help_text="Client phase 1 due date")
    phase_2_due_date = models.DateField(null=True, blank=True, help_text="Client phase 2 due date")
    phase_3_due_date = models.DateField(null=True, blank=True, help_text="Client phase 3 due date")
    phase_4_due_date = models.DateField(null=True, blank=True, help_text="Client phase 4 due date")

    def __str__(self):
        return f"{self.code} - {self.name}"

    def save(self, *args, **kwargs):
        if not self.code:
            base = ''.join(ch for ch in (self.name or 'CENTRE').upper() if ch.isalnum())[:12] or 'CENTRE'
            candidate = base
            suffix = 1
            while CostCentre.objects.filter(code=candidate).exclude(pk=self.pk).exists():
                suffix += 1
                candidate = f"{base[:10]}{suffix}"
            self.code = candidate
        super().save(*args, **kwargs)

    @property
    def total_remaining(self):
        try:
            received = self.get_total_received()
            spent = Decimal(str(self.total_spent)) if self.total_spent else Decimal('0.00')
            return received - spent
        except (InvalidOperation, TypeError):
            return Decimal('0.00')
    
    @property
    def moa_outstanding(self):
        """Calculate MOA Outstanding = MOA Amount - Total Received"""
        try:
            moa = Decimal(str(self.moa_amount)) if self.moa_amount else Decimal('0.00')
            received = self.get_total_received()
            return moa - received
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
    month = models.CharField(max_length=20, blank=True, null=True, help_text="Legacy field - use date_from and date_to instead")
    date_from = models.DateField(blank=True, null=True, help_text="Start date of salary/expenditure period")
    date_to = models.DateField(blank=True, null=True, help_text="End date of salary/expenditure period")
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50, choices=EXPENSE_CATEGORY_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    opening_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    closing_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    oracle_balance = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    expense_id = models.CharField(max_length=100, unique=True, null=True, blank=True, db_index=True, help_text="External/import identifier used to prevent duplicate uploaded expenses")

    @property
    def months_count(self):
        """Calculate number of months between date_from and date_to"""
        if self.date_from and self.date_to:
            # Calculate months between dates (using day difference / 30 for months)
            days_diff = (self.date_to - self.date_from).days
            months = max(1, round(days_diff / 30))  # Min 1 month
            return months
        return 1
    
    @property
    def total_cost(self):
        """Calculate total cost: amount × months"""
        try:
            return Decimal(str(self.amount)) * Decimal(str(self.months_count))
        except (InvalidOperation, TypeError):
            return Decimal(str(self.amount))

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


class BudgetForecast(models.Model):
    """Forecast/draft expenditures before they are released to Monthly Expenditure Tracker"""
    EXPENSE_CATEGORY_CHOICES = [
        ('Salary', 'Salary'),
        ('Bursaries', 'Bursaries'),
        ('Invoices', 'Invoices'),
        ('Fitness', 'Fitness'),
        ('Equipment', 'Equipment/Office Resources'),
        ('Travel', 'Travel'),
    ]

    cost_centre = models.ForeignKey(CostCentre, on_delete=models.CASCADE, related_name='budget_forecasts')
    month = models.CharField(max_length=20, blank=True, null=True, help_text="Legacy field - use date_from and date_to instead")
    date_from = models.DateField(blank=True, null=True, help_text="Start date of salary/expenditure period")
    date_to = models.DateField(blank=True, null=True, help_text="End date of salary/expenditure period")
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=50, choices=EXPENSE_CATEGORY_CHOICES)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    is_released = models.BooleanField(default=False, help_text="True when released to Monthly Expenditure Tracker")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def months_count(self):
        """Calculate number of months between date_from and date_to"""
        if self.date_from and self.date_to:
            days_diff = (self.date_to - self.date_from).days
            months = max(1, round(days_diff / 30))
            return months
        return 1
    
    @property
    def total_cost(self):
        """Calculate total cost: amount × months"""
        try:
            return Decimal(str(self.amount)) * Decimal(str(self.months_count))
        except (InvalidOperation, TypeError):
            return Decimal(str(self.amount))

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Budget Forecast"
        verbose_name_plural = "Budget Forecasts"

    def __str__(self):
        return f"{self.name} ({self.category}) - Forecast {self.created_at.date()}"
        

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

class AuditLog(models.Model):
    """Immutable audit trail for all finance transactions"""
    
    ACTION_CHOICES = [
        ('create_cost_centre', 'Created Cost Centre'),
        ('edit_cost_centre', 'Edited Cost Centre'),
        ('delete_cost_centre', 'Deleted Cost Centre'),
        ('create_expenditure', 'Created Expenditure'),
        ('edit_expenditure', 'Edited Expenditure'),
        ('delete_expenditure', 'Deleted Expenditure'),
        ('create_payment', 'Created Payment'),
        ('delete_payment', 'Deleted Payment'),
    ]
    
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    entity_type = models.CharField(max_length=50)  # 'CostCentre', 'Expenditure', 'Payment'
    entity_id = models.PositiveIntegerField()  # ID of the affected object
    entity_name = models.CharField(max_length=255)  # Readable name/description
    
    # User who made the change
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Previous and new values for edit operations
    previous_values = models.JSONField(default=dict, blank=True)  # Stores old data
    new_values = models.JSONField(default=dict, blank=True)  # Stores new data
    
    # Timestamp (immutable - set only at creation)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['entity_type']),
            models.Index(fields=['action']),
        ]
    
    def __str__(self):
        user_name = self.user.get_full_name() if self.user else "System"
        return f"{self.get_action_display()} - {self.entity_name} by {user_name} at {self.timestamp}"
    
    def save(self, *args, **kwargs):
        # Prevent modifications to existing records
        if self.pk is not None:
            raise ValidationError("Audit logs are immutable and cannot be modified")
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs):
        # Prevent deletion of audit logs
        raise ValidationError("Audit logs are immutable and cannot be deleted")


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
    
    clock_in_time = models.DateTimeField()
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
        return f"{self.employee.username} - {timezone.localtime(self.clock_in_time).strftime('%Y-%m-%d %H:%M')}"
    
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
            return timezone.localtime(self.clock_out_time).strftime('%H:%M:%S')
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


class UserAvailability(models.Model):
    """Track daily availability status for team members"""
    STATUS_CHOICES = [
        ('available', 'Available'),
        ('unavailable', 'Unavailable'),
        ('meeting', 'In Meeting'),
        ('leave', 'On Leave'),
        ('off-hours', 'Off Hours'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='availabilities'
    )
    date = models.DateField(db_index=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, db_index=True)
    
    # Time Fields
    start_time = models.TimeField()
    end_time = models.TimeField()
    
    # Details
    reason = models.TextField(
        blank=True,
        help_text="Why unavailable/meeting title/leave reason"
    )
    meeting_title = models.CharField(max_length=255, blank=True)
    is_personal = models.BooleanField(
        default=False,
        help_text="Private - only admin sees"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='availability_records_created'
    )
    
    class Meta:
        unique_together = [['user', 'date']]
        ordering = ['-date']
        indexes = [
            models.Index(fields=['user', 'date']),
            models.Index(fields=['date']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.date} ({self.status})"
    
    @classmethod
    def get_team_availability(cls, date, exclude_user=None):
        """Get all team members' availability for a specific date"""
        queryset = cls.objects.filter(date=date).select_related('user')
        if exclude_user:
            queryset = queryset.exclude(user=exclude_user)
        return queryset
    
    @classmethod
    def check_conflict(cls, user, date, start_time, end_time, exclude_id=None):
        """Check if proposed time slot conflicts with existing meetings"""
        queryset = cls.objects.filter(
            user=user,
            date=date,
            status='meeting'
        )
        if exclude_id:
            queryset = queryset.exclude(id=exclude_id)
        
        # Check for time overlap
        for availability in queryset:
            if not (end_time <= availability.start_time or start_time >= availability.end_time):
                return True  # Conflict found
        return False


class UserLeaveRequest(models.Model):
    """Track leave/time-off requests with approval workflow"""
    APPROVAL_STATUS = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='leave_requests'
    )
    start_date = models.DateField(db_index=True)
    end_date = models.DateField(db_index=True)
    reason = models.TextField()
    status = models.CharField(
        max_length=20,
        choices=APPROVAL_STATUS,
        default='pending',
        db_index=True
    )
    
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_leaves'
    )
    approval_date = models.DateTimeField(blank=True, null=True)
    rejection_reason = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'start_date']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.user.get_full_name()} - {self.start_date} to {self.end_date} ({self.status})"
    
    def approve(self, approved_by):
        """Approve the leave request and create UserAvailability records"""
        self.status = 'approved'
        self.approved_by = approved_by
        self.approval_date = timezone.now()
        self.save()
        
        # Create UserAvailability records for each day
        current_date = self.start_date
        while current_date <= self.end_date:
            UserAvailability.objects.update_or_create(
                user=self.user,
                date=current_date,
                defaults={
                    'status': 'leave',
                    'start_time': '00:00:00',
                    'end_time': '23:59:59',
                    'reason': self.reason,
                    'created_by': approved_by
                }
            )
            current_date += timedelta(days=1)
    
    def reject(self, rejection_reason=''):
        """Reject the leave request"""
        self.status = 'rejected'
        self.rejection_reason = rejection_reason
        self.save()
