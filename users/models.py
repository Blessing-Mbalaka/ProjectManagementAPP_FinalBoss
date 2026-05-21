from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager

#Custom User Manager
class CustomUserManager(BaseUserManager):
    def create_user(self, username, email=None, password=None, **extra_fields):
        if not username:
            raise ValueError("The Username must be set")
        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')  # ✅ This ensures admins get the correct role

        return self.create_user(username, email, password, **extra_fields)

#Custom User Model
class CustomUser(AbstractUser):
    ROLE_CHOICES = (
        ('admin', 'Admin'),
        ('dean', 'Dean'),
        ('centrehead', 'Centre Head'),
        ('supervisor', 'Supervisor'),
        ('manager', 'Project Manager'),
        ('financialadmin', 'Financial Admin'),
        ('staff', 'Staff'),
        ('student', 'Student'),
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff')
    research_centre = models.ForeignKey(
        'adminpanel.ResearchCentre',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='users',
        help_text="Research centre this user belongs to. Required for centre heads."
    )

    # Use custom manager
    objects = CustomUserManager()
