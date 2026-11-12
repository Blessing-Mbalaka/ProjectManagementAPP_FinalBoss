"""Commit-boundary checks for Admin and Financial Admin finance actions."""
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.db import connection
from django.test import TransactionTestCase
from django.urls import reverse
from adminpanel.models import ResearchCentre, CostCentre, CostCentrePayment, Expenditure, BudgetForecast, FinancialProject, EngagementLog, AuditLog
from projects.models import Project


class FinanceCommitWorkflowTests(TransactionTestCase):
    def setUp(self):
        self.centre = ResearchCentre.objects.create(name='Commit workflow centre')
        User = get_user_model()
        self.admin = User.objects.create_user('commit-admin', role='admin', research_centre=self.centre)
        self.finance = User.objects.create_user('commit-finance', role='financialadmin', research_centre=self.centre)

    def ledger(self, actor, label):
        cc = CostCentre.objects.create(code='COMMIT-' + label[:10], name='Commit ledger ' + label, research_centre=self.centre)
        payment = CostCentrePayment.objects.create(cost_centre=cc, amount='1000.00')
        expense = Expenditure.objects.create(cost_centre=cc, name='Existing expense', category='Equipment', amount='100.00')
        return cc, payment, expense

    def test_delete_populated_cost_centre_commits_and_preserves_client_history(self):
        for actor in [self.admin, self.finance]:
            with self.subTest(role=actor.role):
                cc, payment, expense = self.ledger(actor, actor.role)
                forecast = BudgetForecast.objects.create(cost_centre=cc, name='Planned equipment', category='Equipment', amount='50.00')
                project = Project.objects.create(name='Preserved client work ' + actor.role, created_by=actor, assigned_user=actor, research_centre=self.centre, project_type='financial')
                bid = FinancialProject.objects.create(project=project, owner=actor, research_centre=self.centre, client_name='Commit client', cost_centre=cc, stage='won')
                note = EngagementLog.objects.create(project=project, cost_centre=cc, research_centre=self.centre, entered_by=actor, notes='Preserve client history', client_name='Commit client')
                cc_id = cc.pk
                self.client.force_login(actor)
                response = self.client.post(reverse('delete_cost_centre', args=[cc_id]))
                self.assertEqual(response.status_code, 302)
                connection.check_constraints()
                self.assertFalse(CostCentre.objects.filter(pk=cc_id).exists())
                self.assertFalse(CostCentrePayment.objects.filter(pk=payment.pk).exists())
                self.assertFalse(Expenditure.objects.filter(pk=expense.pk).exists())
                self.assertFalse(BudgetForecast.objects.filter(pk=forecast.pk).exists())
                bid.refresh_from_db(); note.refresh_from_db()
                self.assertIsNone(bid.cost_centre_id)
                self.assertIsNone(note.cost_centre_id)
                self.assertTrue(Project.objects.filter(pk=project.pk).exists())
                self.assertTrue(AuditLog.objects.filter(action='delete_cost_centre', entity_id=cc_id).exists())

    def test_deleting_financial_owner_reports_protected_history_instead_of_500(self):
        project = Project.objects.create(name='Owned financial work', created_by=self.admin, assigned_user=self.finance, research_centre=self.centre)
        FinancialProject.objects.create(project=project, owner=self.finance, research_centre=self.centre, client_name='Protected client')
        self.client.force_login(self.admin)
        response = self.client.post(reverse('delete_user', args=[self.finance.pk]))
        self.assertRedirects(response, reverse('manage_users'))
        self.assertTrue(get_user_model().objects.filter(pk=self.finance.pk).exists())
        self.assertTrue(any('deactivat' in str(message).lower() for message in get_messages(response.wsgi_request)))
        connection.check_constraints()

    def test_add_expenditure_keeps_cached_total_equal_to_saved_spending(self):
        for actor in [self.admin, self.finance]:
            with self.subTest(role=actor.role):
                cc, _, _ = self.ledger(actor, actor.role)
                self.client.force_login(actor)
                response = self.client.post(reverse('add_expenditure'), {'cost_centre_id': cc.pk, 'name': 'Additional equipment', 'category': 'Equipment', 'amount': '25.00', 'date_from': '2026-11-01', 'date_to': '2026-11-30'})
                self.assertEqual(response.status_code, 302)
                self.assertEqual(Expenditure.objects.filter(cost_centre=cc).count(), 2)
                cc.refresh_from_db()
                self.assertEqual(cc.total_spent, Decimal('125.00'))

    def test_deleting_expenditure_recalculates_cached_spending(self):
        for actor in [self.admin, self.finance]:
            with self.subTest(role=actor.role):
                cc, _, expense = self.ledger(actor, actor.role)
                self.client.force_login(actor)
                response = self.client.post(reverse('delete_expenditure', args=[expense.pk]))
                self.assertEqual(response.status_code, 302)
                self.assertFalse(Expenditure.objects.filter(pk=expense.pk).exists())
                cc.refresh_from_db()
                self.assertEqual(cc.total_spent, Decimal('0.00'))
