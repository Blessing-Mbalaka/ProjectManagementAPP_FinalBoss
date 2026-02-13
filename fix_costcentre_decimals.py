#!/usr/bin/env python
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_manage.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from django.db import connection

# First, check what data is corrupted
print("\n=== CHECKING COSTCENTRE DATA ===")
with connection.cursor() as cursor:
    cursor.execute("SELECT id, name, total_received, total_spent, moa_amount FROM adminpanel_costcentre")
    rows = cursor.fetchall()
    for row in rows:
        print(f"ID: {row[0]}, Name: {row[1]}, Received: {row[2]}, Spent: {row[3]}, MOA: {row[4]}")

# Clean all decimal fields to safe defaults
print("\n=== CLEANING COSTCENTRE DATA ===")
with connection.cursor() as cursor:
    cursor.execute("""
        UPDATE adminpanel_costcentre 
        SET total_received = 0.00, total_spent = 0.00, moa_amount = NULL
    """)
    print(f"Cleaned {cursor.rowcount} records")

print("\n=== VERIFYING CLEANED DATA ===")
with connection.cursor() as cursor:
    cursor.execute("SELECT id, name, total_received, total_spent, moa_amount FROM adminpanel_costcentre")
    rows = cursor.fetchall()
    for row in rows:
        print(f"ID: {row[0]}, Name: {row[1]}, Received: {row[2]}, Spent: {row[3]}, MOA: {row[4]}")

print("\n✅ Done!")
