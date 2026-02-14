#!/usr/bin/env python
"""
Populate code values for all cost centres
"""
import sqlite3

db_path = r'c:\Users\bjmba\OneDrive\Desktop\Project Management App\project_manage\db.sqlite3'

print("Connecting to database...")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Get all cost centres
    cursor.execute("SELECT id, name FROM adminpanel_costcentre ORDER BY id")
    cost_centres = cursor.fetchall()
    
    print(f"Found {len(cost_centres)} cost centres")
    print("Populating codes...")
    
    for i, (cc_id, name) in enumerate(cost_centres, 1):
        fake_code = f"CC{i:03d}"
        cursor.execute("UPDATE adminpanel_costcentre SET code = ? WHERE id = ?", (fake_code, cc_id))
        print(f"  {name} → {fake_code}")
    
    conn.commit()
    print(f"\n✓ Successfully populated {len(cost_centres)} codes")
    
except Exception as e:
    print(f"✗ Error: {e}")
    conn.rollback()
finally:
    conn.close()

print("✓ Done!")
