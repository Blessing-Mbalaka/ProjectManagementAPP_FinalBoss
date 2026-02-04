# Test Employee Data Created ✅

## Data Summary

### Employee Accounts Created (5 total)
- **John Doe** - john_doe@example.com - 114 clock records
- **Jane Smith** - jane.smith@example.com - 115 clock records  
- **Mike Johnson** - mike.johnson@example.com - 120 clock records
- **Sarah Williams** - sarah.williams@example.com - 118 clock records
- **David Brown** - david.brown@example.com - 118 clock records

### Clock Records
- **Total Records**: 590 records across all employees
- **Date Range**: Jan 29, 2026 - Feb 4, 2026
- **Distribution**: 5-day work weeks with realistic varying work hours (7-10 hours/day)
- **Patterns**: 
  - Each employee has unique work hours
  - Random variance in start/end times (±15-30 minutes)
  - ~10% random days off/sick days

## Login Credentials for Testing

All test employees have the password: `testpass123`

**Example Login:**
- Username: `john_doe`
- Password: `testpass123`

## Accessing the Dashboard

1. **Start the server:**
   ```bash
   python manage.py runserver
   ```

2. **Open the User Activity Analytics:**
   - Navigate to: `http://127.0.0.1:8000/adminpanel/manage-users/`
   - Admin login required (use your admin account)
   - Scroll to the bottom for the "User Activity Analytics" section

3. **Features to Test:**
   - **Employee Filter**: Select different employees from dropdown
   - **Date Range**: Try 30/60/90 day views
   - **View Types**: Overview, Daily, Weekly, Monthly
   - **Charts**: 
     - Hours Worked (bar chart)
     - Day Distribution (pie chart)
     - Task Progress (horizontal bar)
     - Activity Heatmap (bubble chart)
   - **Tables**:
     - Weekly Summary with breakdown
     - Recent Clock Records

## Data Characteristics

- **Work Hours Distribution**:
  - John Doe: 8-9 hours/day (5 days/week)
  - Jane Smith: 9 hours/day (4 days/week)
  - Mike Johnson: 8 hours/day (5 days/week)
  - Sarah Williams: 9 hours/day (5 days/week)
  - David Brown: 8 hours/day (5 days/week)

- **Realistic Variance**:
  - Arrival times vary ±30 minutes
  - Departure times vary ±15 minutes
  - ~10% random absences (sick days, days off)

## Scripting Details

**Test Data Creation:**
- Script: `create_test_activity_data.py`
- Creates 5 test employee accounts
- Generates 580+ realistic clock-in/out records
- Distributed over ~90 days with weekends excluded

**Verification:**
- Script: `verify_test_data.py`
- Displays total employee and record counts
- Shows distribution per employee
- Confirms date range coverage

## Notes

- All test data uses naive datetimes (may see timezone warnings - these are non-fatal)
- The dashboard aggregates this data in real-time
- API endpoint: `/adminpanel/api/user-activity/`
- All visualizations use Chart.js library

## Next Steps for Testing

1. ✅ Test employee dropdown filter
2. ✅ Test date range selector
3. ✅ Test view type switcher
4. ✅ Verify all 4 charts render with data
5. ✅ Check responsive design on mobile
6. ✅ Test rapid filter changes
7. ✅ Validate calculations (totals, averages)
8. ✅ Check performance with full dataset
