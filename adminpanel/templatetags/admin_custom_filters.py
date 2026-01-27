from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def safe_decimal(value, default='0.00'):
    """
    Safely convert a value to Decimal, returning default if conversion fails
    """
    if value is None or value == '':
        return default
    try:
        result = Decimal(str(value))
        return result
    except (InvalidOperation, ValueError, TypeError):
        return default

@register.filter
def safe_subtract(value, subtrahend):
    """
    Safely subtract two decimal values, returning 0.00 if operation fails
    """
    try:
        val = Decimal(str(value)) if value else Decimal('0.00')
        sub = Decimal(str(subtrahend)) if subtrahend else Decimal('0.00')
        return val - sub
    except (InvalidOperation, ValueError, TypeError):
        return Decimal('0.00')

