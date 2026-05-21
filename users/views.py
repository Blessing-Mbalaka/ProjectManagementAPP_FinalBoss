from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from .forms import CustomUserCreationForm, CustomLoginForm
from .models import CustomUser
from projects.models import StudentProfile
from django.conf import settings
from django.http import HttpResponseForbidden


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
            return redirect('finance') # Centre Head
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
