#!/usr/bin/env python
"""
Remove the code column to allow clean migration
"""
import sqlite3

db_path = r'c:\Users\bjmba\OneDrive\Desktop\Project Management App\project_manage\db.sqlite3'

print("Connecting to database...")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Check if code column exists
    cursor.execute("PRAGMA table_info(adminpanel_costcentre)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'code' in columns:
        print("Removing 'code' column to allow clean migration...")
        # Create backup table
        cursor.execute("""
            CREATE TABLE adminpanel_costcentre_backup AS 
            SELECT id, name, total_received, total_spent, moa_amount 
            FROM adminpanel_costcentre
        """)
        
        # Drop original table
        cursor.execute("DROP TABLE adminpanel_costcentre")
        
        # Rename backup to original
        cursor.execute("ALTER TABLE adminpanel_costcentre_backup RENAME TO adminpanel_costcentre")
        
        conn.commit()
        print("✓ Code column removed, table cleaned")
    else:
        print("✓ Code column doesn't exist, ready for migration")
    
except Exception as e:
    print(f"✗ Error: {e}")
    conn.rollback()
finally:
    conn.close()

print("✓ Database ready for fresh migration!")
