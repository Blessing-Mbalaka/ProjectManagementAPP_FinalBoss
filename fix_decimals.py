#!/usr/bin/env python
"""
Script to fix corrupted decimal values in the database using raw SQL
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'project_manage.settings')
django.setup()

from django.db import connection

def fix_decimals():
    """Fix corrupted decimal values directly in SQLite"""
    cursor = connection.cursor()
    
    try:
        # Get all cost_centres rows with raw SQL
        print("Checking CostCentre table...")
        cursor.execute("SELECT id, name, total_received, total_spent FROM adminpanel_costcentre")
        cost_centres = cursor.fetchall()
        
        for cc_id, name, total_received, total_spent in cost_centres:
            try:
                float(total_received)
                float(total_spent)
                print(f"  ✓ ID {cc_id} ({name}): OK")
            except (ValueError, TypeError):
                print(f"  ✗ ID {cc_id} ({name}): Fixing to 0.00")
                cursor.execute(
                    "UPDATE adminpanel_costcentre SET total_received = '0.00', total_spent = '0.00' WHERE id = ?",
                    [cc_id]
                )
        
        # Check expenditures
        print("\nChecking Expenditure table...")
        cursor.execute("SELECT id, name, amount, opening_balance, closing_balance, oracle_balance FROM adminpanel_expenditure")
        expenditures = cursor.fetchall()
        
        for exp_id, name, amount, opening_balance, closing_balance, oracle_balance in expenditures:
            errors = []
            try:
                float(amount)
            except (ValueError, TypeError):
                errors.append('amount')
            try:
                float(opening_balance)
            except (ValueError, TypeError):
                errors.append('opening_balance')
            try:
                float(closing_balance)
            except (ValueError, TypeError):
                errors.append('closing_balance')
            try:
                float(oracle_balance)
            except (ValueError, TypeError):
                errors.append('oracle_balance')
            
            if errors:
                print(f"  ✗ ID {exp_id} ({name}): Fixing {', '.join(errors)}")
                cursor.execute(
                    """UPDATE adminpanel_expenditure 
                       SET amount = '0.00', opening_balance = '0.00', closing_balance = '0.00', oracle_balance = '0.00' 
                       WHERE id = ?""",
                    [exp_id]
                )
            else:
                print(f"  ✓ ID {exp_id} ({name}): OK")
        
        connection.commit()
        print("\n✓ Database fixed successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
        connection.rollback()

if __name__ == '__main__':
    fix_decimals()
