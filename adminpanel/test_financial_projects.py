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
        self.centre_head = User.objects.create_user(
            username='finance-centre-head', password='pass', role='centrehead', research_centre=self.centre
        )
        self.client.force_login(self.finance_user)

    def create_financial_project(self):
        response = self.client.post(reverse('add_financial_project'), {
            'project_name': 'Digital Training Bid',
            'client_name': 'Example Client',
            'company_name': 'Example Client Holdings (Pty) Ltd',
            'company_registration_number': '2026/123456/07',
            'industry': 'Education',
            'company_website': 'https://example.com',
            'company_email': 'info@example.com',
            'company_phone': '0115550199',
            'company_address': '1 Example Street',
            'contact_name': 'Client Contact',
            'contact_role': 'Procurement Director',
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
        self.assertEqual(record.cost_centre.company_name, 'Example Client Holdings (Pty) Ltd')
        self.assertEqual(record.cost_centre.contact_person_role, 'Procurement Director')
        self.assertIsNone(record.cost_centre.moa_amount)
        self.assertIsNone(record.actual_contract_value)
        self.assertEqual(EngagementLog.objects.get(project=record.project).cost_centre, record.cost_centre)

        duplicate = self.client.post(reverse('convert_financial_project', args=[record.id]), {
            'code': 'CC-2026-102', 'name': 'Duplicate Conversion',
        })
        self.assertRedirects(duplicate, reverse('financial_projects'))
        self.assertEqual(CostCentre.objects.filter(client_name='Example Client').count(), 1)

    def test_actual_contract_value_is_separate_and_can_be_added_after_conversion(self):
        record = self.create_financial_project()
        self.client.post(
            reverse('update_financial_project_stage', args=[record.id]),
            data=json.dumps({'stage': 'won'}), content_type='application/json',
        )
        self.client.post(reverse('convert_financial_project', args=[record.id]), {
            'code': 'CC-2026-200', 'name': 'Confirmed Client Contract',
        })

        response = self.client.post(
            reverse('update_financial_project_contract', args=[record.id]),
            {
                'actual_contract_value': '225000.00',
                'contract_award_date': timezone.localdate().isoformat(),
            },
        )

        self.assertRedirects(response, reverse('financial_projects'))
        record.refresh_from_db()
        record.cost_centre.refresh_from_db()
        self.assertEqual(record.estimated_value, Decimal('250000.00'))
        self.assertEqual(record.actual_contract_value, Decimal('225000.00'))
        self.assertEqual(record.cost_centre.moa_amount, Decimal('225000.00'))

    def test_engagement_workspace_derives_pending_client_without_cost_centre_input(self):
        record = self.create_financial_project()

        response = self.client.post(reverse('manager_engagements'), {
            'project': record.project_id,
            'client_name': '',
            'entry_type': 'discussion',
            'contact_method': 'email',
            'engagement_date': timezone.localdate().isoformat(),
            'subject': 'Pre-award discussion',
            'notes': 'Client requested a revised timetable.',
            'proposal_summary': '',
        })

        self.assertEqual(response.status_code, 302)
        note = EngagementLog.objects.get(project=record.project)
        self.assertEqual(note.client_name, record.client_name)
        self.assertIsNone(note.cost_centre)
        page = self.client.get(reverse('manager_engagements'), {'project': record.project_id})
        self.assertContains(page, 'Cost centre pending · Example Client')
        self.assertNotContains(page, 'name="cost_centre"')

    def test_operational_workflow_diagram_is_visible_on_pipeline_and_notes_pages(self):
        self.create_financial_project()

        pipeline = self.client.get(reverse('financial_projects'))
        notes = self.client.get(reverse('manager_engagements'))

        for response in (pipeline, notes):
            self.assertContains(response, 'How to use the client-to-cost-centre workflow')
            self.assertContains(response, 'No placeholder cost centres')
            self.assertContains(response, 'Add the client opportunity')
            self.assertContains(response, 'Log every engagement')
            self.assertContains(response, 'Wait for official details')
            self.assertContains(response, 'Confirm contract and monitor')

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

    def test_applied_bid_page_tracks_follow_up_and_updates_task_due_date(self):
        record = self.create_financial_project()
        self.client.post(
            reverse('update_financial_project_stage', args=[record.id]),
            data=json.dumps({'stage': 'submitted'}), content_type='application/json',
        )
        follow_up = timezone.localdate() + timedelta(days=5)

        response = self.client.post(reverse('add_financial_project_note', args=[record.id]), {
            'entry_type': 'meeting_minutes',
            'contact_method': 'phone',
            'engagement_date': timezone.localdate().isoformat(),
            'next_follow_up_date': follow_up.isoformat(),
            'notes': 'Client asked us to follow up after committee review.',
        })

        self.assertRedirects(response, reverse('financial_projects'))
        record.refresh_from_db()
        self.assertEqual(record.next_follow_up_date, follow_up)
        self.assertEqual(record.project.tasks.get().due_date, follow_up)
        page = self.client.get(reverse('applied_bids'))
        self.assertContains(page, record.project.name)
        self.assertIn(record, page.context['applied_bids'])
        self.assertContains(page, 'Log follow-up')

    def test_pre_award_company_appears_as_crm_prospect(self):
        record = self.create_financial_project()
        self.client.force_login(self.centre_head)

        response = self.client.get(reverse('crm_tab', args=['clients']))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, record.client_name)
        self.assertContains(response, 'Prospect')
        self.assertContains(response, 'Example Client Holdings (Pty) Ltd')


class LandingClientPipelineAnalyticsTests(TestCase):
    def setUp(self):
        self.centre = ResearchCentre.objects.create(name='Analytics Centre')
        self.other_centre = ResearchCentre.objects.create(name='External Analytics Centre')
        self.head = User.objects.create_user(
            username='analytics-head', password='pass', role='centrehead', research_centre=self.centre
        )
        self.other_head = User.objects.create_user(
            username='analytics-other', password='pass', role='centrehead', research_centre=self.other_centre
        )
        self.admin = User.objects.create_user(username='analytics-admin', password='pass', role='admin')

        self._create_opportunity(self.head, self.centre, 'Won Alpha', 'Alpha Client', 'won')
        self._create_opportunity(self.head, self.centre, 'Pending Alpha', 'Alpha Client', 'proposal')
        self._create_opportunity(self.head, self.centre, 'Lost Beta', 'Beta Client', 'lost')
        self._create_opportunity(self.other_head, self.other_centre, 'External Win', 'External Client', 'won')

    def _create_opportunity(self, owner, centre, project_name, client_name, stage):
        project = Project.objects.create(
            name=project_name,
            project_type='financial',
            created_by=owner,
            assigned_user=owner,
            research_centre=centre,
        )
        return FinancialProject.objects.create(
            project=project,
            owner=owner,
            research_centre=centre,
            client_name=client_name,
            stage=stage,
        )

    def test_centre_head_landing_analytics_are_scoped_and_count_unique_clients(self):
        self.client.force_login(self.head)
        response = self.client.get(reverse('overview'))

        self.assertEqual(response.status_code, 200)
        pipeline = response.context['client_pipeline']
        self.assertEqual(pipeline['approached_clients'], 2)
        self.assertEqual(pipeline['opportunities'], 3)
        self.assertEqual(pipeline['won'], 1)
        self.assertEqual(pipeline['pending'], 1)
        self.assertEqual(pipeline['lost'], 1)
        self.assertEqual(pipeline['decision_win_rate'], 50)
        self.assertContains(response, 'Client Opportunity Pipeline')
        self.assertContains(response, 'Clients approached')

    def test_admin_landing_analytics_include_all_centres(self):
        self.client.force_login(self.admin)
        pipeline = self.client.get(reverse('overview')).context['client_pipeline']

        self.assertEqual(pipeline['approached_clients'], 3)
        self.assertEqual(pipeline['opportunities'], 4)
        self.assertEqual(pipeline['won'], 2)
        self.assertEqual(pipeline['pending'], 1)
        self.assertEqual(pipeline['lost'], 1)
