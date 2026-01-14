#!/usr/bin/env python3
"""
Audit and optionally migrate users in MongoDB.

Usage:
  python backend/scripts/audit_users.py                      # list users and roles
  python backend/scripts/audit_users.py --migrate-user-to-guest  # convert role "user" -> "guest"
"""
import asyncio
import sys
from pathlib import Path
from typing import List

# Ensure backend dir is on sys.path so 'core' absolute imports work
backend_dir = Path(__file__).resolve().parents[1]
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

try:
    # Import backend modules (match runtime import style)
    from core.database import users_collection
except Exception as e:
    print(f"Failed to import backend modules: {e}")
    sys.exit(1)


async def list_users() -> List[dict]:
    users = []
    async for doc in users_collection.find({}, {"email": 1, "role": 1}):
        users.append({"email": doc.get("email"), "role": doc.get("role")})
    return users


async def migrate_user_role_to_guest() -> int:
    result = await users_collection.update_many({"role": "user"}, {"$set": {"role": "guest"}})
    return result.modified_count or 0


async def main():
    migrate = "--migrate-user-to-guest" in sys.argv
    users = await list_users()

    if not users:
        print("No users found in database.")
        return 0

    print("\nUsers in database:")
    print("=" * 40)
    for u in users:
        role = u.get("role")
        email = u.get("email")
        marker = "" if role in ("guest", "editor", "admin") else " (non-standard role)"
        print(f"- {email}  ->  {role}{marker}")

    non_standard = [u for u in users if u.get("role") not in ("guest", "editor", "admin")]
    user_role = [u for u in users if u.get("role") == "user"]

    print("\nSummary:")
    print(f"- Total users: {len(users)}")
    print(f"- With role 'user': {len(user_role)}")
    print(f"- With non-standard roles: {len(non_standard)}")

    if migrate:
        modified = await migrate_user_role_to_guest()
        print(f"\nMigrated {modified} user(s) from role 'user' to 'guest'.")
        users_after = await list_users()
        print("\nRoles after migration:")
        for u in users_after:
            print(f"- {u['email']} -> {u.get('role')}")

    return 0


if __name__ == "__main__":
    try:
        exit(asyncio.run(main()))
    except KeyboardInterrupt:
        print("\nAborted")
        sys.exit(130)

