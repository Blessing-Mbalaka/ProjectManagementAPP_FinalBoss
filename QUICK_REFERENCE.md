# Financial Dashboard Tests - Quick Reference

## 🚀 Quick Start

```bash
# Run all financial dashboard tests
python manage.py test adminpanel.tests.FinancialDashboardTest -v 2
```

## 📂 Test Files Location

```
adminpanel/tests/
├── __init__.py                  (Original tests.py)
├── FinancialDashboardTest.py    (Main test suite - 12 tests)
└── README.md                    (Full documentation)
```

## 📊 Test Data Injected

**3 Cost Centres:**
- Operations: $100,000
- Marketing: $50,000
- Human Resources: $75,000

**9 Expenditures:**
- January & February expenses
- 6 Categories: Salary, Equipment, Travel, Bursaries, Fitness, Invoices

**1 Admin User:**
- Email: admin@test.com
- Password: testpass123

## ✅ Tests Included

### Dashboard Tests (9)
```
✓ test_finance_page_loads - Page loads with 200 status
✓ test_cost_centres_displayed - All cost centres show
✓ test_expenditures_calculated - Expenditures counted
✓ test_category_totals - Categories aggregated
✓ test_monthly_totals - Monthly data grouped
✓ test_cost_centre_remaining_balance - Balance math verified
✓ test_add_new_cost_centre - API POST works
✓ test_add_new_expenditure - Expenditure creation works
✓ test_expenditure_closing_balance_calculation - Auto-calc verified
```

### Integrity Tests (3)
```
✓ test_expenditure_affects_cost_centre_total - Updates cascade
✓ test_multiple_expenditures_sum - Aggregation accurate
✓ test_negative_balance_prevention - Over-budget handled
```

## 🎯 Key Features

- ✅ Comprehensive test data (3 cost centres, 9 expenses)
- ✅ Dashboard functionality testing
- ✅ API endpoint testing
- ✅ Data integrity validation
- ✅ Authentication testing
- ✅ Auto-calculation verification
- ✅ Cascade update testing

## 📖 Documentation

| File | Purpose |
|------|---------|
| adminpanel/tests/README.md | Detailed test documentation |
| TEST_DATA_MAP.md | Visual data structure & API docs |
| FINANCIAL_DASHBOARD_TESTING.md | Complete setup summary |
| QUICK_REFERENCE.md | This file |

## 🔧 Run Options

```bash
# All tests verbose
python manage.py test adminpanel.tests.FinancialDashboardTest -v 2

# Specific test class
python manage.py test adminpanel.tests.FinancialDashboardTest.FinancialDashboardTestData

# Specific test method
python manage.py test adminpanel.tests.FinancialDashboardTest.FinancialDashboardTestData.test_finance_page_loads

# Using test runner script
python scripts/run_financial_tests.py -v 2
python scripts/run_financial_tests.py -t FinancialDashboardTestData
```

## 💰 Test Financial Summary

| Metric | Value |
|--------|-------|
| Total Budget | $225,000 |
| Total Spent (Test Data) | $62,500 |
| Remaining | $162,500 |
| Cost Centres | 3 |
| Expenditures | 9 |
| Months Covered | 2 (Jan, Feb) |

## 🔍 Tested Endpoints

- **GET** `/adminpanel/finance/` ✅ Dashboard view
- **POST** `/adminpanel/add-cost-centre/` ✅ Create cost centre
- **POST** `/adminpanel/add-expenditure/` ✅ Create expenditure

## 📋 Test Data Breakdown

### Operations ($100,000)
```
January:
  - Staff Salaries: $15,000
  - Office Equipment: $5,000
February:
  - Travel Expenses: $3,500
Total: $23,500 spent, $76,500 remaining
```

### Marketing ($50,000)
```
January:
  - Digital Marketing: $8,000
February:
  - Event Sponsorship: $2,500
Total: $10,500 spent, $39,500 remaining
```

### HR ($75,000)
```
January:
  - Bursaries: $20,000
  - Fitness: $1,500
February:
  - Training: $7,000
Total: $28,500 spent, $46,500 remaining
```

## 🛠️ Extending Tests

Add new test in `adminpanel/tests/FinancialDashboardTest.py`:

```python
def test_custom_scenario(self):
    """Test description"""
    # Create/modify test data
    expenditure = Expenditure.objects.create(...)
    
    # Assert expected behavior
    self.assertEqual(expenditure.closing_balance, Decimal('75000.00'))
```

Then run: `python manage.py test adminpanel.tests.FinancialDashboardTest.FinancialDashboardTestData.test_custom_scenario`

## ⚠️ Troubleshooting

**Django not found?**
```bash
pip install -r requirements.txt
```

**Database error?**
```bash
python manage.py migrate
```

**Login issues?**
Check CustomUser model supports email authentication

## 📞 Need Help?

See detailed docs:
- Full test guide: `adminpanel/tests/README.md`
- API reference: `TEST_DATA_MAP.md`
- Setup info: `FINANCIAL_DASHBOARD_TESTING.md`

---

**Tests Created**: 12 test methods across 2 test classes
**Test Data Points**: 13 objects (1 user, 1 profile, 3 cost centres, 9 expenditures)
**Coverage**: Dashboard view, APIs, calculations, integrity
**Status**: ✅ Ready to run
