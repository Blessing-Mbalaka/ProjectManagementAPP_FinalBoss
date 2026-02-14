#!/usr/bin/env python
"""
Direct SQLite script to add code field and inject fake codes
"""
import sqlite3

db_path = r'c:\Users\bjmba\OneDrive\Desktop\Project Management App\project_manage\db.sqlite3'

print("Connecting to database...")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Check if code column already exists
    cursor.execute("PRAGMA table_info(adminpanel_costcentre)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'code' not in columns:
        print("Adding 'code' column to adminpanel_costcentre...")
        cursor.execute("""
            ALTER TABLE adminpanel_costcentre 
            ADD COLUMN code VARCHAR(20) DEFAULT 'TEMP'
        """)
        conn.commit()
        print("✓ Column added")
    else:
        print("✓ 'code' column already exists")
    
    # Get all cost centres
    cursor.execute("SELECT id, name FROM adminpanel_costcentre ORDER BY id")
    cost_centres = cursor.fetchall()
    
    print(f"\nFound {len(cost_centres)} cost centres")
    print("\nInjecting fake codes...")
    
    updated = 0
    for i, (cc_id, name) in enumerate(cost_centres, 1):
        fake_code = f"CC{i:03d}"
        cursor.execute("""
            UPDATE adminpanel_costcentre 
            SET code = ? 
            WHERE id = ?
        """, (fake_code, cc_id))
        print(f"  {name} → {fake_code}")
        updated += 1
    
    conn.commit()
    print(f"\n✓ Successfully injected {updated} fake codes")
    
    # Make code unique by adding constraint info
    print("\nNote: You may need to update migration settings for code uniqueness")
    
except Exception as e:
    print(f"✗ Error: {e}")
    conn.rollback()
finally:
    conn.close()

print("\n✓ All done!")
