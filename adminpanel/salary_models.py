from decimal import Decimal
from django.db import models, transaction
from django.db.models import Sum
from .salary_crypto import PROTECTED_FIELDS, decrypt_fields, encrypt_fields


class SalaryQuerySet(models.QuerySet):
    def aggregate(self, *args, **kwargs):
        result = super().aggregate(*args, **kwargs)
        expressions = {expression.default_alias: expression for expression in args}
        expressions.update(kwargs)
        for key, expression in expressions.items():
            if not isinstance(expression, Sum) or getattr(expression.source_expressions[0], 'name', None) != 'amount':
                continue
            queryset = self.filter(expression.filter) if expression.filter else self
            amounts = [row.amount for row in queryset.iterator()]
            if expression.distinct:
                amounts = list(set(amounts))
            if amounts:
                result[key] = sum(amounts, Decimal('0.00'))
        return result

    def only(self, *fields):
        protected = {field.name for field in self.model._meta.fields} & (set(PROTECTED_FIELDS) | {'salary_ciphertext', 'category'})
        return super().only(*(set(fields) | protected))

    def defer(self, *fields):
        protected = set(PROTECTED_FIELDS) | {'salary_ciphertext', 'category'}
        return super().defer(*(field for field in fields if field not in protected))

    def update(self, **kwargs):
        if (set(kwargs) & (set(PROTECTED_FIELDS) | {'category', 'salary_ciphertext'})):
            if 'salary_ciphertext' in kwargs or any(hasattr(value, 'resolve_expression') for value in kwargs.values()):
                raise ValueError('Use individual model saves for protected salary updates.')
            with transaction.atomic():
                rows = list(self)
                for row in rows:
                    for key, value in kwargs.items():
                        setattr(row, key, value)
                    row.save(update_fields=list(kwargs))
            return len(rows)
        return super().update(**kwargs)

    def bulk_create(self, objs, **kwargs):
        objs = list(objs)
        if any(row.category == 'Salary' for row in objs):
            with transaction.atomic():
                for row in objs:
                    row.save(force_insert=True)
            return objs
        return super().bulk_create(objs, **kwargs)


class SalaryProtectedModel(models.Model):
    salary_ciphertext = models.TextField(blank=True, default='', db_default='')
    objects = SalaryQuerySet.as_manager()

    class Meta:
        abstract = True

    @classmethod
    def from_db(cls, db, field_names, values):
        instance = super().from_db(db, field_names, values)
        if 'salary_ciphertext' in field_names and instance.salary_ciphertext:
            for key, value in decrypt_fields(instance.salary_ciphertext).items():
                if key in field_names:
                    setattr(instance, key, value)
        return instance

    def save(self, *args, **kwargs):
        fields = {field.name for field in self._meta.concrete_fields}
        sensitive = [name for name in PROTECTED_FIELDS if name in fields]
        clear = {key: getattr(self, key) for key in sensitive}
        protected = self.category == 'Salary'
        had_ciphertext = bool(self.salary_ciphertext)
        if protected:
            # Masking storage columns must not bypass the real field validators.
            clear = {key: self._meta.get_field(key).clean(value, self) for key, value in clear.items()}
            self.salary_ciphertext = encrypt_fields(clear)
            for key in sensitive:
                setattr(self, key, 'Protected salary record' if key == 'name' else (None if key == 'oracle_balance' else Decimal('0.00')))
        else:
            self.salary_ciphertext = ''
        if kwargs.get('update_fields') is not None and (protected or had_ciphertext):
            kwargs['update_fields'] = set(kwargs['update_fields']) | set(sensitive) | {'salary_ciphertext'}
        try:
            return super().save(*args, **kwargs)
        finally:
            for key, value in clear.items():
                setattr(self, key, value)
