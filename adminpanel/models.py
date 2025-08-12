from django.conf import settings
from django.db import models
from django.apps import apps
from django.db.models.signals import post_save
from django.dispatch import receiver
from decimal import Decimal


class CostCentre(models.Model):
    name = models.CharField(max_length=100, unique=True)
    total_received = models.DecimalField(max_digits=12, decimal_places=2)
    total_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)

    def __str__(self):
        return self.name

    @property
    def total_remaining(self):
        return self.total_received - self.total_spent


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
        self.amount = Decimal(self.amount)
        self.opening_balance = Decimal(self.opening_balance)
        self.closing_balance = self.opening_balance - self.amount
        super().save(*args, **kwargs)

        # Update CostCentre total_spent
        total = Expenditure.objects.filter(cost_centre=self.cost_centre).aggregate(total=models.Sum('amount'))['total'] or 0
        self.cost_centre.total_spent = total
        self.cost_centre.save()


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


