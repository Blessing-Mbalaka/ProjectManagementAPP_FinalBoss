from decimal import Decimal
import json
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.db import connection
from django.db.models import Sum
from django.test import TestCase, override_settings
from django.urls import reverse
from adminpanel.models import CostCentrePayment, AuditLog, BudgetForecast, CostCentre, Expenditure, ResearchCentre, SecurityEvent, Notification
from adminpanel.audit_service import log_expenditure_creation

U = get_user_model()

@override_settings(STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'}, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class EncryptedSalaryTests(TestCase):
    def setUp(self):
        self.centre = ResearchCentre.objects.create(name='Encrypted payroll centre')
        self.admin = U.objects.create_user('payroll-admin', password='pass', role='admin')
        self.finance = U.objects.create_user('payroll-finance', password='pass', role='financialadmin', research_centre=self.centre)
        self.head = U.objects.create_user('payroll-head', password='pass', role='centrehead', research_centre=self.centre)
        self.cc = CostCentre.objects.create(name='Payroll cost centre', code='PAYENC', research_centre=self.centre, moa_amount=Decimal('100000.00'))
        CostCentrePayment.objects.create(cost_centre=self.cc, amount=Decimal('50000.00'), payment_date='2026-11-01', description='Local payroll test funding')
        self.first = Expenditure.objects.create(cost_centre=self.cc, month='2026-11', name='Private payroll Alice', category='Salary', amount=Decimal('1200.12'), opening_balance=Decimal('5000.00'), oracle_balance=Decimal('1200.12'))
        self.second = Expenditure.objects.create(cost_centre=self.cc, month='2026-11', name='Private payroll Bob', category='Salary', amount=Decimal('2300.34'))
        Expenditure.objects.create(cost_centre=self.cc, name='Non salary supplier', category='Invoices', amount=Decimal('10.00'))

    def test_database_has_ciphertext_and_no_individual_amount_or_balance(self):
        with connection.cursor() as cursor:
            cursor.execute('SELECT name, amount, opening_balance, closing_balance, oracle_balance, salary_ciphertext FROM adminpanel_expenditure WHERE id=%s', [self.first.pk])
            name, amount, opening, closing, oracle, ciphertext = cursor.fetchone()
        self.assertEqual(name, 'Protected salary record')
        self.assertEqual(Decimal(str(amount)), Decimal('0'))
        self.assertEqual(Decimal(str(opening)), Decimal('0'))
        self.assertEqual(Decimal(str(closing)), Decimal('0'))
        self.assertIsNone(oracle)
        self.assertTrue(ciphertext.startswith('gAAAA'))
        self.assertNotIn('1200.12', ciphertext)
        loaded = Expenditure.objects.get(pk=self.first.pk)
        self.assertEqual(loaded.amount, Decimal('1200.12'))
        self.assertEqual(Expenditure.objects.only('amount').get(pk=loaded.pk).amount, loaded.amount)
        self.assertEqual(Expenditure.objects.aggregate(total=Sum('amount'))['total'], Decimal('3510.46'))
        self.assertEqual(Expenditure.objects.aggregate(Sum('amount'))['amount__sum'], Decimal('3510.46'))

    def test_dashboard_and_api_show_salary_totals_without_individual_amounts(self):
        for user in [self.admin, self.finance, self.head]:
            self.client.force_login(user)
            response = self.client.get(reverse('finance'))
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, 'Private payroll')
            self.assertNotContains(response, '1200.12')
            response = self.client.get(reverse('get_expenditures', args=[self.cc.pk]))
            pools = [row for row in response.json()['expenditures'] if row['category'] == 'Salary']
            self.assertEqual(len(pools), 1)
            self.assertEqual(Decimal(str(pools[0]['amount'])), Decimal('3500.46'))
            self.assertIsNone(pools[0]['opening_balance'])
            self.assertIsNone(pools[0]['closing_balance'])

    def test_only_primary_payroll_roles_can_change_salary_records(self):
        self.client.force_login(self.head)
        response = self.client.post(reverse('update_expenditure', args=[self.first.pk]), json.dumps({'amount':'1.00'}), content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.head.is_superuser = True
        self.head.save()
        response = self.client.post(reverse('update_expenditure', args=[self.first.pk]), json.dumps({'amount':'1.00'}), content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.client.force_login(self.finance)
        response = self.client.post(reverse('update_expenditure', args=[self.first.pk]), json.dumps({'amount':'1500.12'}), content_type='application/json')
        self.assertEqual(response.status_code, 200)
        self.first.refresh_from_db()
        self.assertEqual(self.first.amount, Decimal('1500.12'))
        with connection.cursor() as cursor:
            cursor.execute('SELECT amount FROM adminpanel_expenditure WHERE id=%s', [self.first.pk])
            self.assertEqual(Decimal(str(cursor.fetchone()[0])), Decimal('0'))

    def test_forecast_salary_is_encrypted_and_returned_as_protected_pool(self):
        forecast = BudgetForecast.objects.create(cost_centre=self.cc, name='Private forecast Alice', category='Salary', amount=Decimal('50.50'), month='2026-12')
        with connection.cursor() as cursor:
            cursor.execute('SELECT amount, salary_ciphertext FROM adminpanel_budgetforecast WHERE id=%s', [forecast.pk])
            amount, encrypted = cursor.fetchone()
        self.assertEqual(Decimal(str(amount)), Decimal('0'))
        self.assertTrue(encrypted)
        self.client.force_login(self.admin)
        response = self.client.get(reverse('get_budget_forecasts', args=[self.cc.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Private forecast Alice')
        pool = response.json()['forecasts'][0]
        self.assertEqual(pool['total_cost'], 50.5)
        self.assertTrue(pool['is_salary_aggregate'])
        response = self.client.post(reverse('release_budget_forecasts', args=[self.cc.pk]), json.dumps({'forecast_ids':[pool['id']]}), content_type='application/json')
        self.assertEqual(response.status_code, 200, response.content)
        released = Expenditure.objects.filter(category='Salary').order_by('-id').first()
        self.assertEqual(released.amount, Decimal('50.50'))
        self.assertTrue(released.salary_ciphertext)

    def test_salary_audit_contains_no_plaintext_and_key_failure_is_closed(self):
        log_expenditure_creation(self.first, self.admin)
        log = AuditLog.objects.get(entity_id=self.first.pk, action='create_expenditure')
        self.assertNotIn('1200.12', str(log.new_values))
        self.assertNotIn('Private payroll', log.entity_name)
        AuditLog.objects.create(action='create_expenditure', entity_type='Expenditure', entity_id=999, entity_name='Legacy service entry', user=None)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse('finance')).status_code, 200)
        with override_settings(SALARY_ENCRYPTION_KEYS=[]), self.assertRaises(ImproperlyConfigured):
            Expenditure.objects.get(pk=self.first.pk)

    def test_queryset_update_and_bulk_creation_keep_database_encrypted(self):
        Expenditure.objects.filter(pk=self.first.pk).update(amount=Decimal('1300.12'))
        self.assertEqual(Expenditure.objects.get(pk=self.first.pk).amount, Decimal('1300.12'))
        Expenditure.objects.bulk_create([Expenditure(cost_centre=self.cc, name='Bulk salary', category='Salary', amount=Decimal('77.77'))])
        with connection.cursor() as cursor:
            cursor.execute("SELECT amount FROM adminpanel_expenditure WHERE category='Salary'")
            self.assertTrue(all(Decimal(str(row[0])) == 0 for row in cursor.fetchall()))


    def test_key_rotation_keeps_old_values_readable_and_reencrypts_on_save(self):
        from cryptography.fernet import Fernet
        from django.conf import settings
        old_keys = settings.SALARY_ENCRYPTION_KEYS
        new_key = Fernet.generate_key().decode()
        with override_settings(SALARY_ENCRYPTION_KEYS=[new_key] + old_keys):
            row = Expenditure.objects.get(pk=self.first.pk)
            row.save()
            self.assertEqual(Expenditure.objects.get(pk=row.pk).amount, Decimal('1200.12'))
        with self.assertRaises(ImproperlyConfigured):
            Expenditure.objects.get(pk=self.first.pk)


    def test_database_constraint_rejects_plaintext_salary_writes(self):
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('UPDATE adminpanel_expenditure SET amount=%s WHERE id=%s', ['999.99', self.first.pk])
        self.assertEqual(Expenditure.objects.get(pk=self.first.pk).amount, Decimal('1200.12'))


    def test_invalid_private_values_do_not_bypass_field_validation(self):
        from django.core.exceptions import ValidationError
        for value in [Decimal('NaN'), Decimal('10000000000000000.00')]:
            with self.assertRaises(ValidationError):
                BudgetForecast.objects.create(cost_centre=self.cc, name='Invalid private salary', category='Salary', amount=value)
        self.assertFalse(BudgetForecast.objects.exists())


@override_settings(STORAGES={'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'}, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}})
class RoleChangeAlertTests(TestCase):
    def setUp(self):
        self.admin = U.objects.create_user('role-admin', password='pass', role='admin')
        self.it = U.objects.create_user('role-it', password='pass', role='it')
        self.staff = U.objects.create_user('role-staff', password='pass', role='staff')

    def test_authorized_role_change_records_actor_old_and_new_and_notifies_it(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('edit_user', args=[self.staff.pk]), {'username':self.staff.username,'email':'staff@example.test','role':'financialadmin'})
        self.assertEqual(response.status_code, 302)
        event = SecurityEvent.objects.get(event_type='role_change', user=self.staff)
        self.assertEqual(event.details['actor'], self.admin.username)
        self.assertEqual(event.details['before']['role'], 'staff')
        self.assertEqual(event.details['after']['role'], 'financialadmin')
        self.assertIn('Financial Admin', event.reason)
        self.assertTrue(Notification.objects.filter(recipients=self.it, title__startswith='Security flag').exists())

    def test_forged_role_and_session_values_do_not_grant_access(self):
        self.client.force_login(self.staff)
        session = self.client.session
        session['role'] = 'admin'
        session.save()
        response = self.client.post(reverse('edit_user', args=[self.staff.pk]), {'username':self.staff.username,'email':'staff@example.test','role':'admin','is_superuser':'true'})
        self.assertEqual(response.status_code, 403)
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.role, 'staff')
        self.assertFalse(self.staff.is_superuser)
        event = SecurityEvent.objects.filter(event_type='role_change_attempt', user=self.staff).first()
        self.assertTrue(event.details['blocked'])
        self.assertEqual(event.details['requested_role'], 'admin')

    def test_server_side_role_and_superuser_updates_are_also_audited(self):
        U.objects.filter(pk=self.staff.pk).update(role='admin')
        event = SecurityEvent.objects.get(event_type='role_change', user=self.staff)
        self.assertEqual(event.details['after']['role'], 'admin')
        self.staff.refresh_from_db()
        self.staff.is_superuser = True
        self.staff.save(update_fields=['is_superuser'])
        self.assertEqual(SecurityEvent.objects.filter(event_type='role_change', user=self.staff).count(), 2)

    def test_invalid_role_is_rejected(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse('edit_user', args=[self.staff.pk]), {'username':self.staff.username,'email':'staff@example.test','role':'not-a-role'})
        self.assertEqual(response.status_code, 400)
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.role, 'staff')


    def test_permission_group_grant_generates_role_security_alert(self):
        from django.contrib.auth.models import Group
        group = Group.objects.create(name='financial_admin')
        self.staff.groups.add(group)
        event = SecurityEvent.objects.get(event_type='role_change', user=self.staff)
        self.assertIn('financial_admin', event.details['after']['groups'])

    def test_privileged_self_registration_is_denied_and_reported(self):
        self.client.logout()
        response = self.client.post(reverse('register'), {'username':'role-attacker','role':'admin'})
        self.assertEqual(response.status_code, 403)
        self.assertFalse(U.objects.filter(username='role-attacker').exists())
        self.assertTrue(SecurityEvent.objects.filter(event_type='role_change_attempt', details__requested_role='admin').exists())
        self.client.force_login(self.it)
        self.assertEqual(self.client.get(reverse('security_event_audit')).status_code, 200)


    def test_reverse_group_membership_changes_are_audited(self):
        from django.contrib.auth.models import Group
        group = Group.objects.create(name='admin')
        group.user_set.add(self.staff)
        event = SecurityEvent.objects.get(event_type='role_change', user=self.staff)
        self.assertIn('admin', event.details['after']['groups'])
