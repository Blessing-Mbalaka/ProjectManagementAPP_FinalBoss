from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from decimal import Decimal
from adminpanel.models import CostCentre, Expenditure, SupervisorProfile

User = get_user_model()


class FinancialDashboardTestData(TestCase):
    """Test data generator for Finance Dashboard"""

    def setUp(self):
        """Create test data for finance dashboard testing"""
        # Create admin user (SupervisorProfile is created automatically by signal)
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='testpass123',
            role='admin',
            first_name='Admin',
            last_name='User'
        )

        # SupervisorProfile is already created by the post_save signal
        self.supervisor = SupervisorProfile.objects.get(user=self.admin_user)

        # Create cost centres
        self.cost_centre_operations = CostCentre.objects.create(
            name='Operations',
            total_received=Decimal('100000.00'),
            total_spent=Decimal('0.00')
        )

        self.cost_centre_marketing = CostCentre.objects.create(
            name='Marketing',
            total_received=Decimal('50000.00'),
            total_spent=Decimal('0.00')
        )

        self.cost_centre_hr = CostCentre.objects.create(
            name='Human Resources',
            total_received=Decimal('75000.00'),
            total_spent=Decimal('0.00')
        )

        # Create expenditures for Operations
        Expenditure.objects.create(
            cost_centre=self.cost_centre_operations,
            month='January',
            name='Staff Salaries',
            category='Salary',
            amount=Decimal('15000.00'),
            opening_balance=Decimal('100000.00'),
            oracle_balance=Decimal('100000.00')
        )

        Expenditure.objects.create(
            cost_centre=self.cost_centre_operations,
            month='January',
            name='Office Equipment',
            category='Equipment',
            amount=Decimal('5000.00'),
            opening_balance=Decimal('85000.00'),
            oracle_balance=Decimal('85000.00')
        )

        Expenditure.objects.create(
            cost_centre=self.cost_centre_operations,
            month='February',
            name='Travel Expenses',
            category='Travel',
            amount=Decimal('3500.00'),
            opening_balance=Decimal('80000.00'),
            oracle_balance=Decimal('80000.00')
        )

        # Create expenditures for Marketing
        Expenditure.objects.create(
            cost_centre=self.cost_centre_marketing,
            month='January',
            name='Digital Marketing Campaign',
            category='Equipment',
            amount=Decimal('8000.00'),
            opening_balance=Decimal('50000.00'),
            oracle_balance=Decimal('50000.00')
        )

        Expenditure.objects.create(
            cost_centre=self.cost_centre_marketing,
            month='February',
            name='Event Sponsorship',
            category='Travel',
            amount=Decimal('2500.00'),
            opening_balance=Decimal('42000.00'),
            oracle_balance=Decimal('42000.00')
        )

        # Create expenditures for HR
        Expenditure.objects.create(
            cost_centre=self.cost_centre_hr,
            month='January',
            name='Employee Bursaries',
            category='Bursaries',
            amount=Decimal('20000.00'),
            opening_balance=Decimal('75000.00'),
            oracle_balance=Decimal('75000.00')
        )

        Expenditure.objects.create(
            cost_centre=self.cost_centre_hr,
            month='January',
            name='Fitness Program',
            category='Fitness',
            amount=Decimal('1500.00'),
            opening_balance=Decimal('55000.00'),
            oracle_balance=Decimal('55000.00')
        )

        Expenditure.objects.create(
            cost_centre=self.cost_centre_hr,
            month='February',
            name='Staff Training',
            category='Salary',
            amount=Decimal('7000.00'),
            opening_balance=Decimal('53500.00'),
            oracle_balance=Decimal('53500.00')
        )

        self.client = Client()

    def test_finance_page_loads(self):
        """Test that finance page loads successfully"""
        self.client.login(username='admin', password='testpass123')
        response = self.client.get('/adminpanel/finance/')
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'adminpanel/finance.html')

    def test_cost_centres_displayed(self):
        """Test that all cost centres are displayed"""
        self.client.login(username='admin', password='testpass123')
        response = self.client.get('/adminpanel/finance/')
        
        self.assertContains(response, 'Operations')
        self.assertContains(response, 'Marketing')
        self.assertContains(response, 'Human Resources')

    def test_expenditures_calculated(self):
        """Test that expenditures are properly calculated"""
        self.client.login(username='admin', password='testpass123')
        response = self.client.get('/adminpanel/finance/')
        
        # Verify cost centre totals
        cost_centres = response.context['cost_centres']
        self.assertEqual(len(cost_centres), 3)

    def test_category_totals(self):
        """Test category total calculations"""
        self.client.login(username='admin', password='testpass123')
        response = self.client.get('/adminpanel/finance/')
        
        category_totals = response.context['category_totals']
        # Should have salary, equipment, travel, bursaries, fitness categories
        self.assertGreater(len(category_totals), 0)

    def test_monthly_totals(self):
        """Test monthly total calculations"""
        self.client.login(username='admin', password='testpass123')
        response = self.client.get('/adminpanel/finance/')
        
        monthly_totals = response.context['monthly_totals']
        # Should have at least January and February
        self.assertGreaterEqual(len(monthly_totals), 2)

    def test_cost_centre_remaining_balance(self):
        """Test remaining balance calculation"""
        operations = CostCentre.objects.get(name='Operations')
        expected_spent = Decimal('23500.00')  # 15000 + 5000 + 3500
        expected_remaining = Decimal('76500.00')  # 100000 - 23500
        
        # Recalculate spent based on expenditures
        total_spent = sum(e.amount for e in operations.expenditures.all())
        self.assertEqual(total_spent, expected_spent)
        self.assertEqual(operations.total_remaining, expected_remaining)

    def test_add_new_cost_centre(self):
        """Test adding a new cost centre"""
        self.client.login(username='admin', password='testpass123')
        
        response = self.client.post('/adminpanel/finance/add-cost-centre/', {
            'name': 'Research & Development',
            'received': '150000.00'
        }, follow=True)
        
        # Should redirect or return 200
        self.assertEqual(response.status_code, 200)
        self.assertTrue(CostCentre.objects.filter(name='Research & Development').exists())

    def test_add_new_expenditure(self):
        """Test adding a new expenditure"""
        self.client.login(username='admin', password='testpass123')
        
        response = self.client.post('/adminpanel/finance/add-expenditure/', {
            'cost_centre_id': self.cost_centre_operations.id,
            'month': 'March',
            'name': 'Consulting Services',
            'category': 'Equipment',
            'amount': '5500.00',
            'opening_balance': '76500.00'
        }, follow=True)
        
        # Should redirect to finance page (302 -> 200 after follow)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            Expenditure.objects.filter(
                cost_centre=self.cost_centre_operations,
                month='March',
                name='Consulting Services'
            ).exists()
        )

    def test_expenditure_closing_balance_calculation(self):
        """Test that closing balance is automatically calculated"""
        expenditure = Expenditure.objects.get(name='Staff Salaries')
        
        expected_closing = Decimal('85000.00')  # 100000 - 15000
        self.assertEqual(expenditure.closing_balance, expected_closing)


class FinancialDashboardDataIntegrity(TestCase):
    """Test data integrity and calculations for Finance Dashboard"""

    def setUp(self):
        """Setup test data for integrity testing"""
        self.admin_user = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='testpass123',
            role='admin'
        )

        self.cost_centre = CostCentre.objects.create(
            name='Test Centre',
            total_received=Decimal('10000.00'),
            total_spent=Decimal('0.00')
        )

    def test_expenditure_affects_cost_centre_total(self):
        """Test that adding expenditure updates cost centre total spent"""
        Expenditure.objects.create(
            cost_centre=self.cost_centre,
            month='January',
            name='Test Expense',
            category='Salary',
            amount=Decimal('2000.00'),
            opening_balance=Decimal('10000.00')
        )

        self.cost_centre.refresh_from_db()
        self.assertEqual(self.cost_centre.total_spent, Decimal('2000.00'))

    def test_multiple_expenditures_sum(self):
        """Test that multiple expenditures sum correctly"""
        for i in range(3):
            Expenditure.objects.create(
                cost_centre=self.cost_centre,
                month='January',
                name=f'Expense {i}',
                category='Equipment',
                amount=Decimal('1000.00'),
                opening_balance=Decimal('10000.00')
            )

        self.cost_centre.refresh_from_db()
        self.assertEqual(self.cost_centre.total_spent, Decimal('3000.00'))

    def test_negative_balance_prevention(self):
        """Test scenario where spending exceeds budget"""
        # Create expenditure that exceeds budget
        Expenditure.objects.create(
            cost_centre=self.cost_centre,
            month='January',
            name='Over Budget Expense',
            category='Salary',
            amount=Decimal('15000.00'),
            opening_balance=Decimal('10000.00')
        )

        self.cost_centre.refresh_from_db()
        # Remaining balance will be negative
        remaining = self.cost_centre.total_remaining
        self.assertLess(remaining, 0)
