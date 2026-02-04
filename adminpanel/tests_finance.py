from django.test import TestCase, Client
from django.urls import reverse
from decimal import Decimal
from .models import CostCentre, CostCentrePayment, Expenditure
from users.models import CustomUser


class CostCentreModelTests(TestCase):
    """Test CostCentre model with MOA tracking"""
    
    def setUp(self):
        """Set up test data"""
        self.cost_centre = CostCentre.objects.create(
            name='Test Centre',
            total_spent=Decimal('1000.00'),
            moa_amount=Decimal('50000.00')
        )
    
    def test_cost_centre_creation_with_moa(self):
        """Test creating a cost centre with MOA amount"""
        self.assertEqual(self.cost_centre.name, 'Test Centre')
        self.assertEqual(self.cost_centre.moa_amount, Decimal('50000.00'))
        self.assertEqual(self.cost_centre.total_spent, Decimal('1000.00'))
        print("[PASS] Cost centre created with MOA amount")
    
    def test_total_received_calculation(self):
        """Test that total_received is calculated from payments"""
        # Add payments
        CostCentrePayment.objects.create(
            cost_centre=self.cost_centre,
            amount=Decimal('10000.00'),
            description='Payment 1'
        )
        CostCentrePayment.objects.create(
            cost_centre=self.cost_centre,
            amount=Decimal('15000.00'),
            description='Payment 2'
        )
        
        # Refresh from database
        self.cost_centre.refresh_from_db()
        total_received = self.cost_centre.get_total_received()
        
        self.assertEqual(total_received, Decimal('25000.00'))
        self.assertEqual(self.cost_centre.payment_count(), 2)
        print("[PASS] Total received calculated correctly from payments")
    
    def test_total_remaining_calculation(self):
        """Test total_remaining = received - spent"""
        CostCentrePayment.objects.create(
            cost_centre=self.cost_centre,
            amount=Decimal('10000.00'),
            description='Payment'
        )
        
        self.cost_centre.refresh_from_db()
        expected_remaining = Decimal('10000.00') - Decimal('1000.00')
        
        self.assertEqual(self.cost_centre.total_remaining, expected_remaining)
        print("[PASS] Total remaining calculated correctly")
    
    def test_moa_outstanding_calculation(self):
        """Test MOA Outstanding = MOA Amount - Total Received"""
        CostCentrePayment.objects.create(
            cost_centre=self.cost_centre,
            amount=Decimal('20000.00'),
            description='Payment'
        )
        
        self.cost_centre.refresh_from_db()
        expected_outstanding = Decimal('50000.00') - Decimal('20000.00')
        
        self.assertEqual(self.cost_centre.moa_outstanding, expected_outstanding)
        print(f"[PASS] MOA Outstanding calculated correctly: {self.cost_centre.moa_outstanding}")
    
    def test_moa_outstanding_negative(self):
        """Test MOA Outstanding when received exceeds MOA amount"""
        CostCentrePayment.objects.create(
            cost_centre=self.cost_centre,
            amount=Decimal('55000.00'),
            description='Over budget payment'
        )
        
        self.cost_centre.refresh_from_db()
        expected_outstanding = Decimal('50000.00') - Decimal('55000.00')
        
        self.assertEqual(self.cost_centre.moa_outstanding, expected_outstanding)
        self.assertLess(self.cost_centre.moa_outstanding, 0)
        print(f"[PASS] MOA Outstanding correctly negative when over budget: {self.cost_centre.moa_outstanding}")
    
    def test_moa_zero_default(self):
        """Test that MOA amount defaults to 0.00 if not provided"""
        cc = CostCentre.objects.create(name='No MOA Centre')
        self.assertEqual(cc.moa_amount, Decimal('0.00'))
        self.assertEqual(cc.moa_outstanding, Decimal('0.00'))
        print("[PASS] MOA defaults to 0.00 when not provided")


class CostCentreViewTests(TestCase):
    """Test CostCentre views"""
    
    def setUp(self):
        """Set up test user and client"""
        self.client = Client()
        self.user = CustomUser.objects.create_user(
            username='testuser',
            password='testpass123',
            email='test@test.com'
        )
        self.client.login(username='testuser', password='testpass123')
    
    def test_add_cost_centre_with_moa(self):
        """Test adding cost centre via view with MOA amount"""
        response = self.client.post(reverse('add_cost_centre'), {
            'name': 'New Test Centre',
            'received': '5000.00',
            'moa_amount': '25000.00'
        })
        
        # Should redirect to finance page (302 status)
        self.assertEqual(response.status_code, 302)
        
        # Check cost centre was created
        cc = CostCentre.objects.get(name='New Test Centre')
        self.assertEqual(cc.moa_amount, Decimal('25000.00'))
        self.assertEqual(cc.get_total_received(), Decimal('5000.00'))
        print("[PASS] Cost centre added via view with MOA amount")
    
    def test_add_cost_centre_without_moa(self):
        """Test adding cost centre without MOA amount"""
        response = self.client.post(reverse('add_cost_centre'), {
            'name': 'Simple Centre',
            'received': ''
        })
        
        self.assertEqual(response.status_code, 302)
        cc = CostCentre.objects.get(name='Simple Centre')
        self.assertEqual(cc.moa_amount, Decimal('0.00'))
        print("[PASS] Cost centre added without MOA amount")
    
    def test_edit_cost_centre_moa(self):
        """Test editing MOA amount via view"""
        cc = CostCentre.objects.create(
            name='Edit Test Centre',
            moa_amount=Decimal('10000.00')
        )
        
        response = self.client.post(reverse('edit_cost_centre', args=[cc.id]), {
            'name': 'Edit Test Centre',
            'moa_amount': '30000.00'
        })
        
        self.assertEqual(response.status_code, 302)
        cc.refresh_from_db()
        self.assertEqual(cc.moa_amount, Decimal('30000.00'))
        print("[PASS] MOA amount edited successfully via view")
    
    def test_finance_view_shows_moa_data(self):
        """Test that finance view includes MOA data"""
        # Create cost centre with MOA
        cc = CostCentre.objects.create(
            name='View Test Centre',
            moa_amount=Decimal('40000.00')
        )
        CostCentrePayment.objects.create(
            cost_centre=cc,
            amount=Decimal('15000.00')
        )
        
        response = self.client.get(reverse('finance'))
        self.assertEqual(response.status_code, 200)
        
        # Check context data includes cost_centres
        self.assertIn('cost_centres', response.context)
        cost_centres = response.context['cost_centres']
        
        # Find our test centre
        test_cc = next((c for c in cost_centres if c['id'] == cc.id), None)
        self.assertIsNotNone(test_cc)
        self.assertEqual(float(test_cc['moa_amount']), 40000.00)
        self.assertEqual(float(test_cc['moa_outstanding']), 25000.00)  # 40000 - 15000
        print("[PASS] Finance view includes MOA data")


class CostCentrePaymentTests(TestCase):
    """Test CostCentrePayment model"""
    
    def setUp(self):
        self.cc = CostCentre.objects.create(
            name='Payment Test Centre',
            moa_amount=Decimal('50000.00')
        )
    
    def test_payment_creation(self):
        """Test creating a payment"""
        payment = CostCentrePayment.objects.create(
            cost_centre=self.cc,
            amount=Decimal('10000.00'),
            description='Test payment'
        )
        
        self.assertEqual(payment.amount, Decimal('10000.00'))
        self.assertEqual(payment.description, 'Test payment')
        print("[PASS] Payment created successfully")
    
    def test_payment_updates_total_received(self):
        """Test that payment updates cost centre's total_received"""
        self.assertEqual(self.cc.get_total_received(), Decimal('0.00'))
        
        CostCentrePayment.objects.create(
            cost_centre=self.cc,
            amount=Decimal('12000.00')
        )
        
        self.cc.refresh_from_db()
        self.assertEqual(self.cc.get_total_received(), Decimal('12000.00'))
        print("[PASS] Payment updates total_received")
    
    def test_multiple_payments_sum(self):
        """Test that multiple payments are summed correctly"""
        CostCentrePayment.objects.create(cost_centre=self.cc, amount=Decimal('10000.00'))
        CostCentrePayment.objects.create(cost_centre=self.cc, amount=Decimal('5000.00'))
        CostCentrePayment.objects.create(cost_centre=self.cc, amount=Decimal('8000.00'))
        
        self.cc.refresh_from_db()
        self.assertEqual(self.cc.get_total_received(), Decimal('23000.00'))
        print("[PASS] Multiple payments summed correctly")


class IntegrationTests(TestCase):
    """Integration tests for complete workflows"""
    
    def setUp(self):
        self.client = Client()
        self.user = CustomUser.objects.create_user(
            username='integrationuser',
            password='testpass123',
            email='integration@test.com'
        )
        self.client.login(username='integrationuser', password='testpass123')
    
    def test_complete_cost_centre_workflow(self):
        """Test complete workflow: create, add payments, check MOA calculations"""
        # 1. Create cost centre with MOA
        response = self.client.post(reverse('add_cost_centre'), {
            'name': 'Project Alpha',
            'received': '10000.00',
            'moa_amount': '100000.00'
        })
        self.assertEqual(response.status_code, 302)
        
        # 2. Verify creation
        cc = CostCentre.objects.get(name='Project Alpha')
        self.assertEqual(cc.moa_amount, Decimal('100000.00'))
        self.assertEqual(cc.get_total_received(), Decimal('10000.00'))
        self.assertEqual(cc.moa_outstanding, Decimal('90000.00'))
        print("[PASS] Phase 1: Cost centre created with MOA")
        
        # 3. Add more payments
        CostCentrePayment.objects.create(
            cost_centre=cc,
            amount=Decimal('30000.00'),
            description='Phase 2'
        )
        CostCentrePayment.objects.create(
            cost_centre=cc,
            amount=Decimal('25000.00'),
            description='Phase 3'
        )
        cc.refresh_from_db()
        
        # 4. Verify totals
        self.assertEqual(cc.get_total_received(), Decimal('65000.00'))
        self.assertEqual(cc.moa_outstanding, Decimal('35000.00'))
        print("[PASS] Phase 2: Payments added, MOA calculations correct")
        
        # 5. Edit MOA amount
        response = self.client.post(reverse('edit_cost_centre', args=[cc.id]), {
            'name': 'Project Alpha',
            'moa_amount': '80000.00'
        })
        self.assertEqual(response.status_code, 302)
        
        cc.refresh_from_db()
        self.assertEqual(cc.moa_amount, Decimal('80000.00'))
        self.assertEqual(cc.moa_outstanding, Decimal('15000.00'))  # 80000 - 65000
        print("[PASS] Phase 3: MOA amount edited, outstanding recalculated")
        
        # 6. View finance page
        response = self.client.get(reverse('finance'))
        self.assertEqual(response.status_code, 200)
        
        cost_centres = response.context['cost_centres']
        project = next((c for c in cost_centres if c['id'] == cc.id), None)
        
        self.assertIsNotNone(project)
        self.assertEqual(float(project['moa_amount']), 80000.00)
        self.assertEqual(float(project['moa_outstanding']), 15000.00)
        print("[PASS] Phase 4: Finance view shows correct MOA data")
        
        print("\n[SUCCESS] Complete workflow test PASSED [SUCCESS]")


if __name__ == '__main__':
    import unittest
    unittest.main()
