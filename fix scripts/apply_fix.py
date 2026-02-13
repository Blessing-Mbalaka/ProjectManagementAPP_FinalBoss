#!/usr/bin/env python
import re

# Read the file
with open('templates/adminpanel/partials/Staff_Bookings.html', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Fix 1: Find and fix the API_BASE declaration
for i, line in enumerate(lines):
    # Fix typeof check
    if 'if (typeof API_BASE === \'undefined\')' in line:
        lines[i] = line.replace('if (typeof API_BASE === \'undefined\')', 'if (typeof window.API_BASE === \'undefined\')')
        print(f"✓ Fixed line {i+1}: Changed typeof API_BASE check to typeof window.API_BASE")
    
    # Remove const API_BASE declaration
    if 'const API_BASE = window.API_BASE;' in line:
        lines[i] = ''
        print(f"✓ Fixed line {i+1}: Removed const API_BASE redeclaration")
    
    # Fix fetchMonthEvents API_BASE reference
    if 'const url = `${API_BASE}month-events' in line:
        lines[i] = line.replace('${API_BASE}month-events', '${window.API_BASE}month-events')
        print(f"✓ Fixed line {i+1}: Updated fetchMonthEvents to use window.API_BASE")
    
    # Fix loadTeamAvailability API_BASE reference
    if 'const url = `${API_BASE}team-availability' in line:
        lines[i] = line.replace('${API_BASE}team-availability', '${window.API_BASE}team-availability')
        print(f"✓ Fixed line {i+1}: Updated loadTeamAvailability to use window.API_BASE")

# Write back
with open('templates/adminpanel/partials/Staff_Bookings.html', 'w', encoding='utf-8') as f:
    f.writelines(lines)

print("\n✅ All API_BASE fixes applied successfully!")
print("💾 File saved: templates/adminpanel/partials/Staff_Bookings.html")
