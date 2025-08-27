#!/usr/bin/env python3
"""
Script to add an admin user to DTCC-Table
Usage: python add_admin.py <username> <password>
"""

import sys
from app import SessionLocal, User, get_password_hash

def add_admin(username, password):
    db = SessionLocal()
    try:
        # Check if user already exists
        existing_user = db.query(User).filter(User.username == username).first()
        if existing_user:
            print(f"User '{username}' already exists.")
            update = input("Do you want to update them to admin? (y/n): ")
            if update.lower() == 'y':
                existing_user.is_admin = 1
                existing_user.hashed_password = get_password_hash(password)
                db.commit()
                print(f"✅ User '{username}' updated to admin with new password.")
            return
        
        # Create new admin user
        admin_user = User(
            username=username,
            hashed_password=get_password_hash(password),
            is_admin=1
        )
        db.add(admin_user)
        db.commit()
        
        print(f"✅ Admin user created successfully!")
        print(f"Username: {username}")
        print(f"Password: {password}")
        print(f"Status: Admin")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python add_admin.py <username> <password>")
        print("Example: python add_admin.py john mysecretpass123")
        sys.exit(1)
    
    username = sys.argv[1]
    password = sys.argv[2]
    
    add_admin(username, password)