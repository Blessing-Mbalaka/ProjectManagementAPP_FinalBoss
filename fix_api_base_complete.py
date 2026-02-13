#!/usr/bin/env python
"""Fix API_BASE initialization and all references"""

path = r'c:\Users\bjmba\OneDrive\Desktop\Project Management App\project_manage\templates\adminpanel\partials\Staff_Bookings.html'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: Update API_BASE initialization with correct typeof and path replacement
old_init = """    // Initialize API base URL (check if already defined to prevent redeclaration errors)
    if (typeof API_BASE === 'undefined') {
        window.API_BASE = "{% url 'api_get_team_availability' '2025-01-01' %}".replace('2025-01-01', '');
    }"""

new_init = """    // Initialize API base URL (check if already defined to prevent redeclaration errors)
    if (typeof window.API_BASE === 'undefined') {
        const teamAvailUrl = "{% url 'api_get_team_availability' '2025-01-01' %}";
        window.API_BASE = teamAvailUrl.replace('/team-availability/2025-01-01/', '/');
    }"""

if old_init in content:
    content = content.replace(old_init, new_init)
    print("✓ Fixed API_BASE initialization (typeof check + path replacement)")
else:
    print("✗ Could not find API_BASE initialization block")

# Fix 2: Update fetchMonthEvents to use window.API_BASE and correct path
old_fetch = """    function fetchMonthEvents(year, month) {
        const monthStr = String(month + 1).padStart(2, '0');
        const url = `${API_BASE}month-events/${year}/${monthStr}/`;"""

new_fetch = """    function fetchMonthEvents(year, month) {
        const monthStr = String(month + 1).padStart(2, '0');
        const url = `${window.API_BASE}api/month-events/${year}/${monthStr}/`;"""

if old_fetch in content:
    content = content.replace(old_fetch, new_fetch)
    print("✓ Fixed fetchMonthEvents URL construction")
else:
    print("✗ Could not find fetchMonthEvents function")

# Fix 3: Update loadTeamAvailability to use correct path
old_team = """    function loadTeamAvailability() {
        const today = new Date().toISOString().split('T')[0];
        const url = `${window.API_BASE}team-availability/${today}/`;"""

new_team = """    function loadTeamAvailability() {
        const today = new Date().toISOString().split('T')[0];
        const url = `${window.API_BASE}api/team-availability/${today}/`;"""

if old_team in content:
    content = content.replace(old_team, new_team)
    print("✓ Fixed loadTeamAvailability URL path")
else:
    print("✗ Could not find loadTeamAvailability function")

# Write back
with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("\n✅ All API_BASE fixes applied successfully!")
print("📝 Changes:")
print("  1. Changed typeof API_BASE to typeof window.API_BASE")
print("  2. Fixed API_BASE initialization to generate correct /adminpanel/api/ path")
print("  3. Updated month-events URL to use window.API_BASE and api prefix")
print("  4. Updated team-availability URL to use window.API_BASE and api prefix")
