#!/usr/bin/env python3
"""
Create Default Users Script
This script creates default users for the Sign Glove application.
"""

import asyncio
import sys
from datetime import datetime, timezone
from passlib.context import CryptContext
from core.database import users_collection

async def create_default_users():
    """Create default users in the database."""
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    print("🔧 Creating default users...")
    print("=" * 40)
    
    # Default users to create
    default_users = [
        {
            "email": "admin@signglove.com",
            "password": "admin123",
            "role": "admin",
            "description": "Default admin user"
        },
        {
            "email": "editor@signglove.com", 
            "password": "editor123",
            "role": "editor",
            "description": "Default editor user"
        },
        {
            "email": "user@signglove.com",
            "password": "user123", 
            "role": "guest",
            "description": "Default user"
        }
    ]
    
    created_count = 0
    
    for user_data in default_users:
        email = user_data["email"]
        password = user_data["password"]
        role = user_data["role"]
        description = user_data["description"]
        
        # Check if user already exists
        existing_user = await users_collection.find_one({"email": email})
        
        if existing_user:
            print(f"⚠️  User {email} already exists (role: {existing_user.get('role', 'unknown')})")
            continue
        
        # Create new user
        hashed_password = pwd_context.hash(password)
        user_doc = {
            "email": email,
            "password_hash": hashed_password,
            "role": role,
            "created_at": datetime.now(timezone.utc)
        }
        
        result = await users_collection.insert_one(user_doc)
        
        if result.inserted_id:
            print(f"✅ Created {role} user: {email} (password: {password})")
            created_count += 1
        else:
            print(f"❌ Failed to create user: {email}")
    
    print(f"\n📊 Summary:")
    print(f"   Created {created_count} new users")
    print(f"   Total users in database: {await users_collection.count_documents({})}")
    
    print(f"\n🔑 Default Login Credentials:")
    print(f"   Admin: admin@signglove.com / admin123")
    print(f"   Editor: editor@signglove.com / editor123") 
    print(f"   User: user@signglove.com / user123")
    
    print(f"\n⚠️  Security Note: Change these passwords in production!")
    
    return True

async def test_login():
    """Test login with default users."""
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    print(f"\n🧪 Testing login functionality...")
    
    test_email = "admin@signglove.com"
    test_password = "admin123"
    
    # Find user
    user = await users_collection.find_one({"email": test_email})
    
    if not user:
        print(f"❌ Test user not found: {test_email}")
        return False
    
    # Verify password
    if pwd_context.verify(test_password, user.get("password_hash", "")):
        print(f"✅ Login test successful for {test_email}")
        print(f"   Role: {user.get('role', 'unknown')}")
        return True
    else:
        print(f"❌ Password verification failed for {test_email}")
        return False

async def main():
    """Main function."""
    print("🎯 Sign Glove - Default Users Setup")
    print("=" * 50)
    
    try:
        # Create users
        if not await create_default_users():
            return False
        
        # Test login
        if not await test_login():
            return False
        
        print(f"\n🎉 Setup completed successfully!")
        print(f"\n📋 Next steps:")
        print(f"1. Go to http://localhost:5173")
        print(f"2. Login with any of the default credentials above")
        print(f"3. Start using your Sign Glove application!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return False

if __name__ == "__main__":
    try:
        success = asyncio.run(main())
        if not success:
            sys.exit(1)
    except KeyboardInterrupt:
        print("\n👋 Setup interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)
