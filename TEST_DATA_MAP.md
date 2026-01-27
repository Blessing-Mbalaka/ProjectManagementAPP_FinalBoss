# Financial Dashboard Test Data Map

## Directory Structure
```
adminpanel/
├── tests/                               # NEW TEST FOLDER
│   ├── __init__.py                     # Original tests.py moved here
│   ├── FinancialDashboardTest.py       # NEW: Comprehensive test suite
│   └── README.md                        # NEW: Test documentation
├── views.py
├── models.py
└── ...other adminpanel files...

scripts/
└── run_financial_tests.py              # NEW: Test runner utility
```

## Test Data Generated

### Database Setup
```
┌─────────────────────────────────────────────────────────────────┐
│                     TEST DATA STRUCTURE                         │
└─────────────────────────────────────────────────────────────────┘

User
├─ Email: admin@test.com
├─ Password: testpass123
├─ Role: admin
└─ SupervisorProfile
   ├─ Department: Finance
   ├─ Office: Building A, Room 101
   └─ Title: Dr.

CostCentres (3)
│
├─ Operations [$100,000.00]
│  ├─ Expenditures:
│  │  ├─ January: Staff Salaries ($15,000) → Salary
│  │  ├─ January: Office Equipment ($5,000) → Equipment
│  │  └─ February: Travel Expenses ($3,500) → Travel
│  ├─ Total Spent: $23,500.00
│  └─ Remaining: $76,500.00
│
├─ Marketing [$50,000.00]
│  ├─ Expenditures:
│  │  ├─ January: Digital Marketing ($8,000) → Equipment
│  │  └─ February: Event Sponsorship ($2,500) → Travel
│  ├─ Total Spent: $10,500.00
│  └─ Remaining: $39,500.00
│
└─ Human Resources [$75,000.00]
   ├─ Expenditures:
   │  ├─ January: Employee Bursaries ($20,000) → Bursaries
   │  ├─ January: Fitness Program ($1,500) → Fitness
   │  └─ February: Staff Training ($7,000) → Salary
   ├─ Total Spent: $28,500.00
   └─ Remaining: $46,500.00
```

## Test Coverage Map

### Dashboard Functionality Tests
```
FinancialDashboardTestData
├─ test_finance_page_loads()
│  └─ Verifies: HTTP 200, template rendering
├─ test_cost_centres_displayed()
│  └─ Verifies: All 3 cost centres in response
├─ test_expenditures_calculated()
│  └─ Verifies: 9 expenditures counted
├─ test_category_totals()
│  └─ Verifies: 6 expense categories aggregated
├─ test_monthly_totals()
│  └─ Verifies: January & February data
├─ test_cost_centre_remaining_balance()
│  └─ Verifies: Math (received - spent = remaining)
├─ test_add_new_cost_centre()
│  └─ Verifies: POST /adminpanel/add-cost-centre/
├─ test_add_new_expenditure()
│  └─ Verifies: POST /adminpanel/add-expenditure/
└─ test_expenditure_closing_balance_calculation()
   └─ Verifies: Auto-calculation of closing balance
```

### Data Integrity Tests
```
FinancialDashboardDataIntegrity
├─ test_expenditure_affects_cost_centre_total()
│  └─ Verifies: Cascade updates to parent
├─ test_multiple_expenditures_sum()
│  └─ Verifies: Sum accuracy across multiple records
└─ test_negative_balance_prevention()
   └─ Verifies: Over-budget scenario handling
```

## API Endpoints Tested

### 1. Finance Dashboard View
```
GET /adminpanel/finance/

Context Data Returned:
├─ cost_centres: QuerySet[CostCentre]
├─ all_expenditures: QuerySet[Expenditure]
├─ category_totals: [{category, total}]
└─ monthly_totals: [{month, total}]
```

### 2. Add Cost Centre Endpoint
```
POST /adminpanel/add-cost-centre/

Request Body:
├─ name: str (required)
└─ received: Decimal (required)

Response: JSON
└─ {message: "Cost Centre added successfully"}
```

### 3. Add Expenditure Endpoint
```
POST /adminpanel/add-expenditure/

Request Body:
├─ cost_centre_id: int (required)
├─ month: str (required)
├─ name: str (required)
├─ category: str (required, choices: Salary|Bursaries|Invoices|Fitness|Equipment|Travel)
├─ amount: Decimal (required)
└─ opening_balance: Decimal (required)

Response: JSON
└─ Auto-calculates: closing_balance = opening_balance - amount
```

## Running the Tests

### Quick Start
```bash
# From project_manage directory
python manage.py test adminpanel.tests.FinancialDashboardTest -v 2
```

### Using Test Runner Script
```bash
# Run all financial tests
python scripts/run_financial_tests.py -v 2

# Run specific test class
python scripts/run_financial_tests.py -t FinancialDashboardTestData

# Run specific test method
python scripts/run_financial_tests.py -t FinancialDashboardTestData.test_finance_page_loads
```

## Expense Categories Reference

| Category | Purpose | Test Data |
|----------|---------|-----------|
| Salary | Staff compensation | $22,000 (Jan: $15k, Feb: $7k) |
| Equipment | Office resources & equipment | $13,000 (Jan: $5k + $8k) |
| Travel | Travel expenses | $6,000 (Feb: $3.5k + $2.5k) |
| Bursaries | Student/employee bursaries | $20,000 (Jan) |
| Fitness | Fitness programs | $1,500 (Jan) |
| Invoices | General invoices | $0 (configured, no test data) |

## Monthly Breakdown

### January Expenditures
```
Operations:     Staff Salaries ($15,000) + Equipment ($5,000) = $20,000
Marketing:      Digital Campaign ($8,000) = $8,000
HR:             Bursaries ($20,000) + Fitness ($1,500) = $21,500
─────────────────────────────────────────────────────────────────
TOTAL JANUARY:  $49,500
```

### February Expenditures
```
Operations:     Travel ($3,500) = $3,500
Marketing:      Event Sponsorship ($2,500) = $2,500
HR:             Training ($7,000) = $7,000
─────────────────────────────────────────────────────────────────
TOTAL FEBRUARY: $13,000
```

### Grand Totals
```
Total Budget:   $225,000.00
Total Spent:    $62,500.00
Total Remaining: $162,500.00
```

## Key Testing Features

✅ **Realistic Test Data** - Multiple cost centres with varied expenses
✅ **Cascading Updates** - Cost centre totals auto-update
✅ **Decimal Precision** - All financial math uses Decimal type
✅ **Authentication** - Tests verify login requirements
✅ **API Testing** - Both GET and POST endpoints covered
✅ **Edge Cases** - Includes over-budget scenario testing
✅ **Data Integrity** - Validates calculation accuracy
✅ **Monthly Aggregation** - Tests time-based grouping
✅ **Category Analysis** - Tests expense categorization

## Notes for Developers

1. **Test Isolation**: Each test method gets fresh data via setUp()
2. **Database**: Uses Django's test database (in-memory by default)
3. **Authentication**: Uses Django's test client with login()
4. **Decimal Handling**: All monetary values use Decimal to avoid floating-point errors
5. **Auto-Calculations**: Closing balance calculated on save()
6. **Related Fields**: Cost centre totals updated via signals

## Integration with CI/CD

To integrate with CI/CD pipeline:

```bash
# Run tests with coverage
coverage run --source='adminpanel' manage.py test adminpanel.tests.FinancialDashboardTest
coverage report

# Run tests and generate XML report
python manage.py test adminpanel.tests.FinancialDashboardTest --failfast
```

## Extending the Tests

See [adminpanel/tests/README.md](../tests/README.md) for examples of adding custom test scenarios.
