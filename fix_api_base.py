# Fix API_BASE declaration error in Staff_Bookings.html

with open('templates/adminpanel/partials/Staff_Bookings.html', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix 1: Remove const API_BASE declaration
old1 = """    if (typeof API_BASE === 'undefined') {
        window.API_BASE = "{% url 'api_get_team_availability' '2025-01-01' %}".replace('2025-01-01', '');
    }
    const API_BASE = window.API_BASE;"""

new1 = """    if (typeof window.API_BASE === 'undefined') {
        window.API_BASE = "{% url 'api_get_team_availability' '2025-01-01' %}".replace('2025-01-01', '');
    }"""

if old1 in content:
    content = content.replace(old1, new1)
    print("✓ Fixed API_BASE initialization - removed const redeclaration")
else:
    print("⚠ Warning: Could not find exact match for Fix 1")

# Fix 2: Replace API_BASE with window.API_BASE in fetchMonthEvents
old2 = "const url = `${API_BASE}month-events/${year}/${monthStr}/`;"
new2 = "const url = `${window.API_BASE}month-events/${year}/${monthStr}/`;"
if old2 in content:
    content = content.replace(old2, new2)
    print("✓ Fixed fetchMonthEvents - using window.API_BASE")
else:
    print("⚠ Warning: Could not find exact match for Fix 2")

# Fix 3: Replace API_BASE with window.API_BASE in loadTeamAvailability  
old3 = "const url = `${API_BASE}team-availability/${today}/`;"
new3 = "const url = `${window.API_BASE}team-availability/${today}/`;"
if old3 in content:
    content = content.replace(old3, new3)
    print("✓ Fixed loadTeamAvailability - using window.API_BASE")
else:
    print("⚠ Warning: Could not find exact match for Fix 3")

# Write back
with open('templates/adminpanel/partials/Staff_Bookings.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("\n✅ All API_BASE fixes applied successfully!")
