"""Authenticated encryption of individual salary fields with an external key."""
from decimal import Decimal
import json
from cryptography.fernet import Fernet, MultiFernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

NUMERIC_FIELDS = ('amount', 'opening_balance', 'closing_balance', 'oracle_balance')
PROTECTED_FIELDS = ('name',) + NUMERIC_FIELDS


def cipher():
    keys = settings.SALARY_ENCRYPTION_KEYS
    if not keys:
        raise ImproperlyConfigured('Configure SALARY_ENCRYPTION_KEYS before storing or migrating salary data.')
    try:
        return MultiFernet([Fernet(key.encode() if isinstance(key, str) else key) for key in keys])
    except (TypeError, ValueError):
        raise ImproperlyConfigured('SALARY_ENCRYPTION_KEYS must contain valid Fernet keys.') from None


def encrypt_fields(values):
    return cipher().encrypt(json.dumps({key: None if value is None else str(value) for key, value in values.items()}).encode()).decode()


def decrypt_fields(token):
    try:
        values = json.loads(cipher().decrypt(token.encode()).decode())
        return {key: (Decimal(value) if key in NUMERIC_FIELDS and value is not None else value) for key, value in values.items()}
    except (InvalidToken, ValueError, TypeError):
        raise ImproperlyConfigured('Salary data cannot be decrypted with the configured keys. No plaintext fallback is allowed.') from None


def unseal_row(category, token, values):
    return {**values, **decrypt_fields(token)} if category == 'Salary' and token else values


def can_manage_salaries(user):
    # A superuser flag or group name does not grant payroll access to another role.
    return bool(user.is_authenticated and user.is_active and user.role in {'admin', 'financialadmin'})
