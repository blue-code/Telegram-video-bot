import asyncio
import os
import sys

# Ensure current directory is in sys.path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), 'venv311/lib/python3.11/site-packages'))

# Import src.db which should trigger the patch
from src.db import get_database

async def main():
    print("Starting connection test...")
    try:
        db = await get_database()
        print("Obtained database object.")
        print("Attempting ping command...")
        # A simple command to force connection
        await db.command("ping")
        print("Ping successful!")
    except Exception as e:
        print(f"Connection error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
