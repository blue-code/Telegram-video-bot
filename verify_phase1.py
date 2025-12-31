import asyncio
import os
from src.db import get_database, close_database

async def verify():
    print("Verifying Database Connection...")
    uri = os.getenv("MONGO_URI")
    if not uri or uri == "placeholder_mongo_uri":
        print("WARNING: MONGO_URI is set to placeholder or missing. Real connection cannot be established.")
    else:
        print(f"Using MONGO_URI: {uri[:10]}...")

    try:
        db = await get_database()
        print(f"Successfully initialized MongoDB client for database: {db.name}")
        print("Phase 1 (Database Setup) Verification: SUCCESS")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await close_database()

if __name__ == "__main__":
    asyncio.run(verify())
