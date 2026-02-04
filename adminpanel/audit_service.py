"""
Audit logging service for finance transactions
Provides immutable audit trail for all changes
"""
from adminpanel.models import AuditLog
from django.db import transaction
import json


def create_audit_log(action, entity_type, entity_id, entity_name, user, previous_values=None, new_values=None):
    """
    Create an immutable audit log entry
    
    Args:
        action: Action type (from ACTION_CHOICES)
        entity_type: Type of entity ('CostCentre', 'Expenditure', 'Payment')
        entity_id: ID of the affected object
        entity_name: Readable name/description
        user: User who made the change
        previous_values: Dict of old values (for edit operations)
        new_values: Dict of new values (for edit operations)
    """
    try:
        with transaction.atomic():
            AuditLog.objects.create(
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                entity_name=entity_name,
                user=user,
                previous_values=previous_values or {},
                new_values=new_values or {}
            )
    except Exception as e:
        print(f"Error creating audit log: {e}")


def log_cost_centre_creation(cost_centre, user):
    """Log creation of a cost centre"""
    values = {
        'name': cost_centre.name,
        'moa_amount': str(cost_centre.moa_amount)
    }
    create_audit_log(
        action='create_cost_centre',
        entity_type='CostCentre',
        entity_id=cost_centre.id,
        entity_name=cost_centre.name,
        user=user,
        new_values=values
    )


def log_cost_centre_edit(cost_centre, user, previous_values):
    """Log edit of a cost centre"""
    new_values = {
        'name': cost_centre.name,
        'moa_amount': str(cost_centre.moa_amount)
    }
    create_audit_log(
        action='edit_cost_centre',
        entity_type='CostCentre',
        entity_id=cost_centre.id,
        entity_name=cost_centre.name,
        user=user,
        previous_values=previous_values,
        new_values=new_values
    )


def log_cost_centre_deletion(cost_centre_id, cost_centre_name, user):
    """Log deletion of a cost centre"""
    create_audit_log(
        action='delete_cost_centre',
        entity_type='CostCentre',
        entity_id=cost_centre_id,
        entity_name=cost_centre_name,
        user=user
    )


def log_expenditure_creation(expenditure, user):
    """Log creation of an expenditure"""
    values = {
        'cost_centre': expenditure.cost_centre.name,
        'month': expenditure.month,
        'name': expenditure.name,
        'category': expenditure.category,
        'amount': str(expenditure.amount)
    }
    create_audit_log(
        action='create_expenditure',
        entity_type='Expenditure',
        entity_id=expenditure.id,
        entity_name=f"{expenditure.name} ({expenditure.category}) - {expenditure.month}",
        user=user,
        new_values=values
    )


def log_expenditure_edit(expenditure, user, previous_values):
    """Log edit of an expenditure"""
    new_values = {
        'month': expenditure.month,
        'name': expenditure.name,
        'category': expenditure.category,
        'amount': str(expenditure.amount)
    }
    create_audit_log(
        action='edit_expenditure',
        entity_type='Expenditure',
        entity_id=expenditure.id,
        entity_name=f"{expenditure.name} ({expenditure.category}) - {expenditure.month}",
        user=user,
        previous_values=previous_values,
        new_values=new_values
    )


def log_expenditure_deletion(expenditure_id, expenditure_name, user):
    """Log deletion of an expenditure"""
    create_audit_log(
        action='delete_expenditure',
        entity_type='Expenditure',
        entity_id=expenditure_id,
        entity_name=expenditure_name,
        user=user
    )


def log_payment_creation(payment, user):
    """Log creation of a payment"""
    values = {
        'cost_centre': payment.cost_centre.name,
        'amount': str(payment.amount),
        'description': payment.description,
        'payment_date': str(payment.payment_date)
    }
    create_audit_log(
        action='create_payment',
        entity_type='Payment',
        entity_id=payment.id,
        entity_name=f"{payment.cost_centre.name} - R {payment.amount}",
        user=user,
        new_values=values
    )


def log_payment_deletion(payment_id, payment_description, user):
    """Log deletion of a payment"""
    create_audit_log(
        action='delete_payment',
        entity_type='Payment',
        entity_id=payment_id,
        entity_name=payment_description,
        user=user
    )
