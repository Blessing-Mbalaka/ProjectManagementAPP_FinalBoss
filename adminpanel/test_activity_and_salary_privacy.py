import io
import zipfile
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from projects.models import Project
from users.models import CustomUser

from .models import CostCentre, Expenditure, PageVisitLog, ResearchCentre


class PageVisitAuditTests(TestCase):
    def setUp(self):
        self.centre_a = ResearchCentre.objects.create(name='Audit Centre A')
        self.centre_b = ResearchCentre.objects.create(name='Audit Centre B')
        self.admin = CustomUser.objects.create_user('audit-admin', password='pass', role='admin')
        self.head = CustomUser.objects.create_user(
            'audit-head', password='pass', role='centrehead', research_centre=self.centre_a
        )
        self.user_a = CustomUser.objects.create_user(
            'audit-user-a', password='pass', role='manager', research_centre=self.centre_a
        )
        self.user_b = CustomUser.objects.create_user(
            'audit-user-b', password='pass', role='manager', research_centre=self.centre_b
        )

    def test_middleware_logs_successful_html_page_without_query_string(self):
        self.client.force_login(self.user_a)
        path = reverse('manager_dashboard')
        response = self.client.get(f'{path}?private_filter=do-not-store')
        self.assertEqual(response.status_code, 200)
        visit = PageVisitLog.objects.get(user=self.user_a, path=path)
        self.assertNotIn('private_filter', visit.path)
        self.assertEqual(visit.method, 'GET')

    def test_json_api_is_not_recorded(self):
        self.client.force_login(self.user_a)
        path = reverse('get_user_notifications')
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PageVisitLog.objects.filter(user=self.user_a, path=path).exists())

    def test_admin_sees_all_centres_but_centre_head_is_scoped(self):
        PageVisitLog.objects.create(user=self.user_a, path='/centre-a-private-page/')
        PageVisitLog.objects.create(user=self.user_b, path='/centre-b-private-page/')

        self.client.force_login(self.admin)
        response = self.client.get(reverse('page_visit_audit'))
        self.assertContains(response, '/centre-a-private-page/')
        self.assertContains(response, '/centre-b-private-page/')

        self.client.force_login(self.head)
        response = self.client.get(reverse('page_visit_audit'))
        self.assertContains(response, '/centre-a-private-page/')
        self.assertNotContains(response, '/centre-b-private-page/')

    def test_regular_user_cannot_view_audit_page(self):
        self.client.force_login(self.user_a)
        self.assertEqual(self.client.get(reverse('page_visit_audit')).status_code, 403)


class SalaryPrivacyTests(TestCase):
    def setUp(self):
        self.admin = CustomUser.objects.create_user('salary-admin', password='pass', role='admin')
        self.cost_centre = CostCentre.objects.create(code='SAL001', name='Salary Test Centre')
        Expenditure.objects.create(
            cost_centre=self.cost_centre,
            month='2026-10',
            name='Private Employee Alice',
            category='Salary',
            amount=Decimal('100.00'),
        )
        Expenditure.objects.create(
            cost_centre=self.cost_centre,
            month='2026-10',
            name='Private Employee Bob',
            category='Salary',
            amount=Decimal('200.00'),
        )
        Expenditure.objects.create(
            cost_centre=self.cost_centre,
            month='2026-10',
            name='Visible Supplier',
            category='Invoices',
            amount=Decimal('50.00'),
        )

    def test_salary_names_are_replaced_but_financial_totals_are_unchanged(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse('finance'))
        self.assertEqual(response.status_code, 200)

        rows = response.context['all_expenditures']
        salary_rows = [row for row in rows if row['category'] == 'Salary']
        self.assertEqual(len(salary_rows), 1)
        self.assertEqual(salary_rows[0]['amount'], 300.0)
        self.assertEqual(salary_rows[0]['salary_record_count'], 2)
        self.assertTrue(salary_rows[0]['is_salary_aggregate'])
        self.assertTrue(salary_rows[0]['name'].startswith('Protected salary pool #'))
        self.assertEqual(response.context['finance_summary']['total_expenditure'], 350.0)
        self.assertNotContains(response, 'Private Employee Alice')
        self.assertNotContains(response, 'Private Employee Bob')
        self.assertContains(response, 'Visible Supplier')
        self.assertContains(response, '2 salary records combined')

        api_response = self.client.get(reverse('get_expenditures', args=[self.cost_centre.id]))
        self.assertEqual(api_response.status_code, 200)
        api_rows = api_response.json()['expenditures']
        api_salary_rows = [row for row in api_rows if row['category'] == 'Salary']
        self.assertEqual(len(api_salary_rows), 1)
        self.assertEqual(float(api_salary_rows[0]['amount']), 300.0)
        self.assertNotContains(api_response, 'Private Employee Alice')
        self.assertNotContains(api_response, 'Private Employee Bob')

        export_response = self.client.get(reverse('download_finance_summary_excel'))
        self.assertEqual(export_response.status_code, 200)
        with zipfile.ZipFile(io.BytesIO(export_response.content)) as workbook:
            exported_xml = '\n'.join(
                workbook.read(name).decode('utf-8')
                for name in workbook.namelist()
                if name.startswith('xl/worksheets/')
            )
        self.assertNotIn('Private Employee Alice', exported_xml)
        self.assertNotIn('Private Employee Bob', exported_xml)
        self.assertIn('Protected salary pool #', exported_xml)
        self.assertIn('300.00', exported_xml)


class ManagerGanttLayoutTests(TestCase):
    def setUp(self):
        centre = ResearchCentre.objects.create(name='Manager Gantt Centre')
        self.manager = CustomUser.objects.create_user(
            'gantt-manager', password='pass', role='manager', research_centre=centre
        )
        self.other = CustomUser.objects.create_user(
            'other-manager', password='pass', role='manager', research_centre=centre
        )
        Project.objects.create(name='Visible Manager Project', created_by=self.manager, assigned_user=self.manager)
        Project.objects.create(name='Other Private Project', created_by=self.other, assigned_user=self.other)

    def test_manager_gantt_uses_fitted_layout_and_preserves_project_scope(self):
        self.client.force_login(self.manager)
        response = self.client.get(reverse('manager_ganttchart'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'adminpanel/admin_ganttchart.html')
        self.assertContains(response, 'My Project Timeline')
        self.assertContains(response, 'Back to Dashboard')
        self.assertContains(response, 'id="fitGantt"')
        self.assertContains(response, 'id="toggleGanttSidebar"')
        self.assertContains(response, 'Visible Manager Project')
        self.assertNotContains(response, 'Other Private Project')
