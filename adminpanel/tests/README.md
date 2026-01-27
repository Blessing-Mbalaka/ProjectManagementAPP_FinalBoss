# Financial Dashboard Test Suite

## Overview
This test suite provides comprehensive testing for the Finance Dashboard functionality of the Project Management App. It includes test data generation and validation of all financial calculations and operations.

## Test Structure

### Location
```
adminpanel/tests/
├── __init__.py                      # Main tests file (moved from tests.py)
├── FinancialDashboardTest.py        # Comprehensive financial tests and test data
└── README.md                        # This file
```

## Test Data Generated

The test suite automatically creates the following test data:

### Cost Centres (3)
1. **Operations** - $100,000.00 budget
2. **Marketing** - $50,000.00 budget
3. **Human Resources** - $75,000.00 budget

### Expenditures (9 total)
- January & February expenses across all cost centres
- Multiple expense categories: Salary, Equipment, Travel, Bursaries, Fitness

### Test User
- **Email**: admin@test.com
- **Password**: testpass123
- **Role**: admin

## Running the Tests

### Run All Financial Tests
```bash
cd project_manage
python manage.py test adminpanel.tests.FinancialDashboardTest -v 2
```

### Run Specific Test Class
```bash
# Test data and dashboard functionality
python manage.py test adminpanel.tests.FinancialDashboardTest.FinancialDashboardTestData -v 2

# Test data integrity and calculations
python manage.py test adminpanel.tests.FinancialDashboardTest.FinancialDashboardDataIntegrity -v 2
```

### Run Specific Test Method
```bash
# Test finance page loads
python manage.py test adminpanel.tests.FinancialDashboardTest.FinancialDashboardTestData.test_finance_page_loads -v 2

# Test cost centre calculations
python manage.py test adminpanel.tests.FinancialDashboardTest.FinancialDashboardTestData.test_cost_centre_remaining_balance -v 2
```

## Test Classes

### FinancialDashboardTestData
Tests the core functionality of the finance dashboard with realistic test data.

**Test Methods:**
- `test_finance_page_loads()` - Verify dashboard page loads with 200 status
- `test_cost_centres_displayed()` - Verify all cost centres appear in response
- `test_expenditures_calculated()` - Verify expenditure calculations
- `test_category_totals()` - Verify category-based totals
- `test_monthly_totals()` - Verify monthly aggregations
- `test_cost_centre_remaining_balance()` - Verify balance calculations
- `test_add_new_cost_centre()` - Test cost centre creation API
- `test_add_new_expenditure()` - Test expenditure creation API
- `test_expenditure_closing_balance_calculation()` - Verify balance math

### FinancialDashboardDataIntegrity
Tests data integrity and mathematical accuracy of financial calculations.

**Test Methods:**
- `test_expenditure_affects_cost_centre_total()` - Verify updates cascade
- `test_multiple_expenditures_sum()` - Verify aggregation accuracy
- `test_negative_balance_prevention()` - Test over-budget scenarios

## Sample Test Data Summary

### Cost Centre: Operations
- Opening Balance: $100,000.00
- January Expenses: $20,000.00 (Salaries + Equipment)
- February Expenses: $3,500.00 (Travel)
- Total Spent: $23,500.00
- Remaining: $76,500.00

### Cost Centre: Marketing
- Opening Balance: $50,000.00
- January Expenses: $8,000.00 (Digital Campaign)
- February Expenses: $2,500.00 (Event Sponsorship)
- Total Spent: $10,500.00
- Remaining: $39,500.00

### Cost Centre: Human Resources
- Opening Balance: $75,000.00
- January Expenses: $21,500.00 (Bursaries + Fitness)
- February Expenses: $7,000.00 (Training)
- Total Spent: $28,500.00
- Remaining: $46,500.00

## API Endpoints Tested

- **GET** `/adminpanel/finance/` - Finance dashboard view
- **POST** `/adminpanel/add-cost-centre/` - Add new cost centre
- **POST** `/adminpanel/add-expenditure/` - Add new expenditure

## Expense Categories Tested

- **Salary** - Staff compensation
- **Equipment** - Equipment and office resources
- **Travel** - Travel expenses
- **Bursaries** - Student/employee bursaries
- **Fitness** - Fitness programs
- **Invoices** - General invoices

## Notes

1. **Test Data Isolation**: Each test case creates fresh test data in setUp()
2. **Authentication**: Tests include login verification
3. **Decimal Precision**: All monetary values use Django's Decimal for accuracy
4. **Cascading Updates**: Cost centre totals update automatically when expenditures change
5. **Closing Balance**: Calculated as `opening_balance - amount`

## Extending the Tests

To add new test cases:

```python
def test_custom_scenario(self):
    """Test a custom financial scenario"""
    # Create or modify test data
    expenditure = Expenditure.objects.create(
        cost_centre=self.cost_centre_operations,
        month='March',
        name='Custom Expense',
        category='Equipment',
        amount=Decimal('5000.00'),
        opening_balance=Decimal('80000.00')
    )
    
    # Assert expected behavior
    self.assertEqual(expenditure.closing_balance, Decimal('75000.00'))
```

## Troubleshooting

### Django Not Installed
Ensure virtual environment is activated and Django is installed:
```bash
pip install -r requirements.txt
```

### Database Issues
Reset test database:
```bash
python manage.py flush --noinput
python manage.py migrate
```

### Login Issues
Verify CustomUser model supports email login in authentication settings.

## Related Documentation
- [Finance Dashboard Views](../views.py)
- [Financial Models](../models.py)
- [Finance Templates](../../templates/adminpanel/finance.html)
