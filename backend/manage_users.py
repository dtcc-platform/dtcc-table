#!/usr/bin/env python3
"""
Interactive user management script for DTCC-Table
"""

from app import SessionLocal, User, get_password_hash

def list_users():
    """List all users"""
    db = SessionLocal()
    try:
        users = db.query(User).all()
        print("\n📋 Current Users:")
        print("-" * 50)
        for user in users:
            status = "Admin" if user.is_admin else "Regular"
            print(f"ID: {user.id} | Username: {user.username} | Status: {status}")
        print("-" * 50)
    finally:
        db.close()

def add_user(username, password, is_admin=False):
    """Add a new user"""
    db = SessionLocal()
    try:
        existing = db.query(User).filter(User.username == username).first()
        if existing:
            print(f"❌ User '{username}' already exists")
            return False
        
        user = User(
            username=username,
            hashed_password=get_password_hash(password),
            is_admin=1 if is_admin else 0
        )
        db.add(user)
        db.commit()
        
        status = "Admin" if is_admin else "Regular"
        print(f"✅ {status} user '{username}' created successfully!")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def delete_user(username):
    """Delete a user"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            print(f"❌ User '{username}' not found")
            return False
        
        if username == "vasnas":
            print("❌ Cannot delete the primary admin user")
            return False
        
        db.delete(user)
        db.commit()
        print(f"✅ User '{username}' deleted successfully!")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def reset_password(username, new_password):
    """Reset user password"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            print(f"❌ User '{username}' not found")
            return False
        
        user.hashed_password = get_password_hash(new_password)
        db.commit()
        print(f"✅ Password reset for '{username}' successfully!")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def make_admin(username):
    """Promote user to admin"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.username == username).first()
        if not user:
            print(f"❌ User '{username}' not found")
            return False
        
        if user.is_admin:
            print(f"ℹ️ User '{username}' is already an admin")
            return True
        
        user.is_admin = 1
        db.commit()
        print(f"✅ User '{username}' promoted to admin!")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        db.rollback()
        return False
    finally:
        db.close()

def interactive_menu():
    """Interactive menu for user management"""
    while True:
        print("\n🔧 DTCC-Table User Management")
        print("=" * 50)
        print("1. List all users")
        print("2. Add regular user")
        print("3. Add admin user")
        print("4. Delete user")
        print("5. Reset password")
        print("6. Promote to admin")
        print("0. Exit")
        print("=" * 50)
        
        choice = input("\nEnter your choice: ").strip()
        
        if choice == "1":
            list_users()
        
        elif choice == "2":
            username = input("Enter username: ").strip()
            password = input("Enter password: ").strip()
            add_user(username, password, is_admin=False)
        
        elif choice == "3":
            username = input("Enter username: ").strip()
            password = input("Enter password: ").strip()
            add_user(username, password, is_admin=True)
        
        elif choice == "4":
            username = input("Enter username to delete: ").strip()
            confirm = input(f"Are you sure you want to delete '{username}'? (y/n): ")
            if confirm.lower() == 'y':
                delete_user(username)
        
        elif choice == "5":
            username = input("Enter username: ").strip()
            password = input("Enter new password: ").strip()
            reset_password(username, password)
        
        elif choice == "6":
            username = input("Enter username to promote: ").strip()
            make_admin(username)
        
        elif choice == "0":
            print("Goodbye! 👋")
            break
        
        else:
            print("❌ Invalid choice. Please try again.")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # Command line mode
        if sys.argv[1] == "list":
            list_users()
        elif sys.argv[1] == "add-admin" and len(sys.argv) == 4:
            add_user(sys.argv[2], sys.argv[3], is_admin=True)
        elif sys.argv[1] == "add-user" and len(sys.argv) == 4:
            add_user(sys.argv[2], sys.argv[3], is_admin=False)
        elif sys.argv[1] == "delete" and len(sys.argv) == 3:
            delete_user(sys.argv[2])
        elif sys.argv[1] == "reset-password" and len(sys.argv) == 4:
            reset_password(sys.argv[2], sys.argv[3])
        elif sys.argv[1] == "make-admin" and len(sys.argv) == 3:
            make_admin(sys.argv[2])
        else:
            print("Usage:")
            print("  python manage_users.py                    # Interactive mode")
            print("  python manage_users.py list               # List all users")
            print("  python manage_users.py add-admin <username> <password>")
            print("  python manage_users.py add-user <username> <password>")
            print("  python manage_users.py delete <username>")
            print("  python manage_users.py reset-password <username> <password>")
            print("  python manage_users.py make-admin <username>")
    else:
        # Interactive mode
        interactive_menu()