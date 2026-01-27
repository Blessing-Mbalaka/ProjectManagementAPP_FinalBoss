"""
URL configuration for project_manage project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from adminpanel.views import overview
from adminpanel.views_media import get_media_file
from users.views import login_view
from projects.views import dashboard
from manager.views import manager_dashboard


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', login_view, name='login'), 
    path("dashboard/", dashboard, name='dashboard'),  # Dashboard Home
    path("users/", include("users.urls")),      # User-related URLs
    path("projects/", include("projects.urls")),  # Projects-related URLs
    path("adminpanel/", include("adminpanel.urls")),  # Admin-related URLs
    path('overview/', overview, name='overview'),
    path('manager_dashboard/', manager_dashboard, name='manager_dashboard'),
    path('manager/', include('manager.urls')),  # Manager-related URLs
    # Custom media serving with filesystem/database fallback
    re_path(r'^media/(?P<path>.*)$', get_media_file),
]
