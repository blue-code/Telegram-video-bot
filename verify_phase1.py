import asyncio
import os
from src.db import get_database, close_database

async def verify():
    print("Verifying Supabase Database Connection...")
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        print("ERROR: SUPABASE_URL or SUPABASE_KEY is missing in .env!")
        return

    print(f"Using Supabase URL: {url[:20]}...")

    try:
        sb = await get_database()
        # Attempt a simple query to verify connection
        # We try to select from 'videos' table (even if empty)
        await sb.table("videos").select("*", count="exact").limit(1).execute()
        print("Successfully connected to Supabase and verified 'videos' table.")
        print("Phase 1 (Database Setup) Verification: SUCCESS")
    except Exception as e:
        print(f"Error connecting to Supabase: {e}")
        print("Make sure you have created the 'videos' table in Supabase SQL Editor.")
    finally:
        await close_database()

if __name__ == "__main__":
    asyncio.run(verify())