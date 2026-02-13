path = r'c:\Users\bjmba\OneDrive\Desktop\Project Management App\project_manage\templates\adminpanel\partials\Staff_Bookings.html'
with open(path, 'r', encoding='utf-8') as f:
    c = f.read()

# Fix typeof check
c = c.replace(
    "if (typeof API_BASE === 'undefined')",
    "if (typeof window.API_BASE === 'undefined')"
)
print("✓ Fixed typeof check")

# Fix API_BASE initialization  
old_api = 'window.API_BASE = "{% url \'api_get_team_availability\' \'2025-01-01\' %}".replace(\'2025-01-01\', \'\');'
new_api = 'const teamAvailUrl = "{% url \'api_get_team_availability\' \'2025-01-01\' %}"; window.API_BASE = teamAvailUrl.replace(\'/team-availability/2025-01-01/\', \'/\');'
c = c.replace(old_api, new_api)
print("✓ Fixed API_BASE path initialization")

# Fix month-events URL
c = c.replace(
    'const url = `${API_BASE}month-events/${year}/${monthStr}/`;',
    'const url = `${window.API_BASE}api/month-events/${year}/${monthStr}/`;'
)
print("✓ Fixed month-events URL")

# Fix team-availability URL
c = c.replace(
    'const url = `${window.API_BASE}team-availability/${today}/`;',
    'const url = `${window.API_BASE}api/team-availability/${today}/`;'
)
print("✓ Fixed team-availability URL")

with open(path, 'w', encoding='utf-8') as f:
    f.write(c)

print("\n✅ ALL FIXES APPLIED")
