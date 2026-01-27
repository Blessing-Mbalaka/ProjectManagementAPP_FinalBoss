#!/usr/bin/env python
import os
import sys
import django

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_manage.settings')
sys.path.insert(0, os.path.dirname(__file__))

django.setup()

from django.core.management import call_command

call_command('makemigrations', 'adminpanel', verbosity=2)
