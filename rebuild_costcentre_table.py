#!/usr/bin/env python
"""
Properly rebuild CostCentre table with code column
"""
import sqlite3

db_path = r'c:\Users\bjmba\OneDrive\Desktop\Project Management App\project_manage\db.sqlite3'

print("Connecting to database...")
conn = sqlite3.connect(db_path)
conn.execute("PRAGMA foreign_keys = OFF")
cursor = conn.cursor()

try:
    # Get all foreign keys info
    print("Recreating CostCentre table with code column...")
    
    # Backup data
    cursor.execute("""
        CREATE TABLE adminpanel_costcentre_backup AS 
        SELECT id, name, total_received, total_spent, moa_amount 
        FROM adminpanel_costcentre
    """)
    
    # Drop original table
    cursor.execute("DROP TABLE adminpanel_costcentre")
    
    # Create new table with code column
    cursor.execute("""
        CREATE TABLE adminpanel_costcentre (
            id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
            code VARCHAR(20),
            name VARCHAR(100) UNIQUE NOT NULL,
            total_received DECIMAL(12, 2) DEFAULT 0.00 NOT NULL,
            total_spent DECIMAL(12, 2) DEFAULT 0.00 NOT NULL,
            moa_amount DECIMAL(12, 2) DEFAULT NULL
        )
    """)
    
    # Restore data
    cursor.execute("""
        INSERT INTO adminpanel_costcentre (id, name, total_received, total_spent, moa_amount)
        SELECT id, name, total_received, total_spent, moa_amount 
        FROM adminpanel_costcentre_backup
    """)
    
    # Drop backup
    cursor.execute("DROP TABLE adminpanel_costcentre_backup")
    
    conn.commit()
    print("✓ Table recreated successfully")
    
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()
    conn.rollback()
finally:
    conn.execute("PRAGMA foreign_keys = ON")
    conn.close()

print("✓ Done!")
