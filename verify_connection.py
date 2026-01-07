import asyncio
import os
import logging
from src.db import get_database
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

async def check():
    print("Checking DB connection...")
    try:
        db = await get_database()
        print("Got DB object, sending ping...")
        # Force a connection
        await db.command('ping')
        print("Ping successful! Connection verified.")
    except Exception as e:
        print(f"Connection failed: {e}")

if __name__ == "__main__":
    asyncio.run(check())
