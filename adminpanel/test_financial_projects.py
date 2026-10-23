import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from adminpanel.models import CostCentre, EngagementLog, FinancialProject, ResearchCentre
from projects.models import Project, Task


User = get_user_model()


class FinancialProjectWorkflowTests(TestCase):
    def setUp(self):
        self.centre = ResearchCentre.objects.create(name='Financial Workflow Centre')
        self.other_centre = ResearchCentre.objects.create(name='Other Financial Centre')
        self.finance_user = User.objects.create_user(
            username='finance-owner', password='pass', role='financialadmin', research_centre=self.centre
        )
        self.other_finance_user = User.objects.create_user(
            username='finance-other', password='pass', role='financialadmin', research_centre=self.centre
        )
        self.external_finance_user = User.objects.create_user(
            username='finance-external', password='pass', role='financialadmin', research_centre=self.other_centre
        )
        self.client.force_login(self.finance_user)

    def create_financial_project(self):
        response = self.client.post(reverse('add_financial_project'), {
            'project_name': 'Digital Training Bid',
            'client_name': 'Example Client',
            'contact_name': 'Client Contact',
            'contact_email': 'client@example.com',
            'contact_phone': '0115550100',
            'estimated_value': '250000.00',
            'bid_deadline': (timezone.localdate() + timedelta(days=21)).isoformat(),
            'summary': 'Training delivery proposal.',
        })
        self.assertRedirects(response, reverse('financial_projects'))
        return FinancialProject.objects.get(project__name='Digital Training Bid')

    def test_create_bid_assigns_project_and_monitoring_task_to_financial_admin(self):
        record = self.create_financial_project()

        self.assertEqual(record.owner, self.finance_user)
        self.assertEqual(record.project.assigned_user, self.finance_user)
        self.assertEqual(record.project.project_type, 'financial')
        task = record.project.tasks.get()
        self.assertEqual(task.assigned_to, self.finance_user)
        self.assertEqual(task.status, 'todo')
        self.assertContains(self.client.get(reverse('financial_kanban')), task.title)

    def test_financial_admin_pipeline_is_owner_scoped(self):
        own_record = self.create_financial_project()
        other_project = Project.objects.create(
            name='Other Owner Bid', project_type='financial', created_by=self.other_finance_user,
            assigned_user=self.other_finance_user, research_centre=self.centre,
        )
        FinancialProject.objects.create(
            project=other_project, owner=self.other_finance_user,
            research_centre=self.centre, client_name='Private Client',
        )

        response = self.client.get(reverse('financial_projects'))

        self.assertContains(response, own_record.client_name)
        self.assertNotContains(response, 'Private Client')

    def test_bid_stage_updates_linked_task_and_project(self):
        record = self.create_financial_project()

        response = self.client.post(
            reverse('update_financial_project_stage', args=[record.id]),
            data=json.dumps({'stage': 'submitted'}),
            content_type='application/json',
        )

        self.assertEqual(response.status_code, 200)
        record.refresh_from_db()
        record.project.refresh_from_db()
        task = record.project.tasks.get()
        self.assertEqual(record.stage, 'submitted')
        self.assertEqual(record.project.status, 'in-progress')
        self.assertEqual(task.status, 'review')
        self.assertEqual(task.progress, 66)

    def test_engagement_note_can_be_saved_before_cost_centre(self):
        record = self.create_financial_project()

        response = self.client.post(reverse('add_financial_project_note', args=[record.id]), {
            'entry_type': 'meeting_minutes',
            'subject': 'Discovery meeting',
            'notes': 'Client confirmed the requested delivery scope.',
            'proposal_summary': 'Three-phase training programme.',
        })

        self.assertRedirects(response, reverse('financial_projects'))
        note = EngagementLog.objects.get(project=record.project)
        self.assertIsNone(note.cost_centre)
        self.assertEqual(note.client_label, 'Example Client')
        self.assertEqual(note.entered_by, self.finance_user)

    def test_won_bid_converts_once_and_preserves_engagement_history(self):
        record = self.create_financial_project()
        self.client.post(reverse('add_financial_project_note', args=[record.id]), {
            'entry_type': 'discussion', 'notes': 'Proposal accepted.'
        })
        self.client.post(
            reverse('update_financial_project_stage', args=[record.id]),
            data=json.dumps({'stage': 'won'}), content_type='application/json',
        )

        response = self.client.post(reverse('convert_financial_project', args=[record.id]), {
            'code': 'CC-2026-101', 'name': 'Example Client Training',
        })

        self.assertRedirects(response, reverse('financial_projects'))
        record.refresh_from_db()
        self.assertIsNotNone(record.cost_centre_id)
        self.assertEqual(record.cost_centre.client_name, 'Example Client')
        self.assertEqual(record.cost_centre.moa_amount, Decimal('250000.00'))
        self.assertEqual(EngagementLog.objects.get(project=record.project).cost_centre, record.cost_centre)

        duplicate = self.client.post(reverse('convert_financial_project', args=[record.id]), {
            'code': 'CC-2026-102', 'name': 'Duplicate Conversion',
        })
        self.assertRedirects(duplicate, reverse('financial_projects'))
        self.assertEqual(CostCentre.objects.filter(client_name='Example Client').count(), 1)

    def test_financial_admin_cannot_update_another_owners_task(self):
        other_project = Project.objects.create(
            name='Another Financial Owner Project', created_by=self.other_finance_user,
            assigned_user=self.other_finance_user, research_centre=self.centre,
        )
        other_task = Task.objects.create(
            project=other_project, assigned_to=self.other_finance_user,
            created_by=self.other_finance_user, title='Private financial task',
        )

        response = self.client.post(
            reverse('update_task_status', args=[other_task.id]),
            data=json.dumps({'status': 'done'}), content_type='application/json',
        )

        self.assertEqual(response.status_code, 404)
        other_task.refresh_from_db()
        self.assertEqual(other_task.status, 'todo')
