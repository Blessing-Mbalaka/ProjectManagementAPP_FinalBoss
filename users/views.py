from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.views import PasswordResetView
import logging
from .forms import CustomUserCreationForm, CustomLoginForm, StrictPasswordResetForm
from .models import CustomUser
from projects.models import StudentProfile
from django.conf import settings
from django.http import HttpResponseForbidden

logger = logging.getLogger(__name__)


def register_view(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            role = request.POST.get('role')

            # Prevent public self-registration into privileged roles
            if role in ['admin', 'dean', 'centrehead', 'financialadmin']:
                form.add_error(None, "You are not allowed to register with this role.")
                return render(request, 'users/register.html', {'form': form})

            user = form.save(commit=False)
            user.role = role
            user.save()

            # Automatically create StudentProfile if role is student
            if role == 'student':
                supervisor = CustomUser.objects.filter(role='admin').first()
                StudentProfile.objects.create(user=user, supervisor=supervisor)

            return redirect('login')
    else:
        form = CustomUserCreationForm()
    return render(request, 'users/register.html', {'form': form})



def login_view(request):
    form = CustomLoginForm(data=request.POST or None)
    if form.is_valid():
        user = form.get_user()
        login(request, user)

        # Redirect based on user role
        if user.role == 'admin':
            return redirect('overview') # Admin
        elif user.role == 'dean':
            return redirect('overview') # Dean
        elif user.role == 'centrehead':
            return redirect('overview') # Centre Head
        elif user.role == 'supervisor':
            return redirect('supervisor_dashboard_portal') # Supervisor Portal
        elif user.role == 'manager':
            return redirect('manager_dashboard') # Project Manager
        elif user.role == 'financialadmin':
            return redirect('finance_readonly') # Financial Admin
        elif user.role == 'student':
            return redirect('student_dashboard')  # Student
        else:
            return redirect('dashboard') # Staff
    return render(request, 'users/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('login')


class DebugPasswordResetView(PasswordResetView):
    template_name = 'users/password_reset.html'
    email_template_name = 'users/password_reset_email.html'
    subject_template_name = 'users/password_reset_subject.txt'
    form_class = StrictPasswordResetForm

    def form_valid(self, form):
        email = form.cleaned_data.get('email', '').strip()
        matching_users = list(form.get_users(email))
        self.from_email = getattr(settings, 'EMAIL_HOST_USER', '') or getattr(settings, 'DEFAULT_FROM_EMAIL', None)
        logger.info("Password reset requested for %s. Matching active users: %s", email, len(matching_users))
        logger.info("Password reset sender resolved to %s", self.from_email)
        if not matching_users:
            logger.warning("Password reset blocked. No active user found for email %s", email)
            form.add_error('email', 'We could not find an active account with that email address.')
            return self.form_invalid(form)

        if not self.from_email:
            logger.error("Password reset blocked. No SMTP sender address is configured.")
            form.add_error(None, 'Password reset email is not configured correctly on the server.')
            return self.form_invalid(form)

        try:
            response = super().form_valid(form)
            logger.info("Password reset email sent successfully for %s", email)
            return response
        except Exception as exc:
            logger.exception("Password reset email failed for %s", email)
            form.add_error(None, f"We could not send the reset email. Reason: {exc}")
            return self.form_invalid(form)
