path = r'c:\Users\bjmba\OneDrive\Desktop\Project Management App\project_manage\templates\adminpanel\partials\Staff_Bookings.html'
with open(path, 'r', encoding='utf-8') as f:
    c = f.read()

# Fix: Remove 'api/' prefix from URLs since API_BASE already ends with '/api/'
c = c.replace(
    'const url = `${window.API_BASE}api/month-events/${year}/${monthStr}/`;',
    'const url = `${window.API_BASE}month-events/${year}/${monthStr}/`;'
)
print("✓ Fixed month-events URL (removed duplicate api/)")

c = c.replace(
    'const url = `${window.API_BASE}api/team-availability/${today}/`;',
    'const url = `${window.API_BASE}team-availability/${today}/`;'
)
print("✓ Fixed team-availability URL (removed duplicate api/)")

with open(path, 'w', encoding='utf-8') as f:
    f.write(c)

print("\n✅ URL PATHS CORRECTED")
