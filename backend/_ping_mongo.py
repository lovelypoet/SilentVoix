import asyncio
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient

# Ensure this script can import backend modules when run from repo root
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

from core.settings import settings  # noqa: E402

async def main() -> None:
    print(f"MONGO_URI from settings: {settings.MONGO_URI}")
    print(f"DB_NAME from settings: {settings.DB_NAME}")
    try:
        client = AsyncIOMotorClient(settings.MONGO_URI, serverSelectionTimeoutMS=10000)
        await client.admin.command("ping")
        print("Ping successful")
    except Exception as exc:
        print("Ping failed")
        # Show full exception chain
        import traceback
        traceback.print_exc()
        # Print helpful hints
        print("\nHints:")
        print("- Ensure your IP is allowed in Atlas Network Access")
        print("- Verify username/password in MONGO_URI")
        print("- Use mongodb+srv:// URI for Atlas with correct cluster name and database name")
        print("- If behind a firewall or proxy, allow outbound TLS (443) and MongoDB ports")

if __name__ == "__main__":
    asyncio.run(main()) 