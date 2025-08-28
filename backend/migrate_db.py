#!/usr/bin/env python3
"""
Database migration script to add processed_size column
Run this on your deployment to update the existing database
"""

import sqlite3
import os
import shutil
from datetime import datetime

def migrate_database():
    db_path = 'users.db'
    
    # Check if database exists
    if not os.path.exists(db_path):
        print("❌ Database not found. The application will create it automatically on first run.")
        return
    
    # Create backup
    backup_path = f'users_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
    shutil.copy(db_path, backup_path)
    print(f"✅ Created backup: {backup_path}")
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Check if column already exists
        cursor.execute("PRAGMA table_info(uploaded_files)")
        columns = cursor.fetchall()
        column_names = [col[1] for col in columns]
        
        if 'processed_size' in column_names:
            print("✅ Column 'processed_size' already exists. No migration needed.")
        else:
            # Add the new column
            cursor.execute("ALTER TABLE uploaded_files ADD COLUMN processed_size VARCHAR")
            conn.commit()
            print("✅ Added 'processed_size' column to uploaded_files table")
            print("✅ Migration completed successfully!")
    
    except sqlite3.OperationalError as e:
        if "no such table: uploaded_files" in str(e):
            print("ℹ️ Table 'uploaded_files' doesn't exist yet. It will be created on first run.")
        else:
            print(f"❌ Error during migration: {e}")
            print(f"ℹ️ Restore from backup if needed: {backup_path}")
            return
    
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()