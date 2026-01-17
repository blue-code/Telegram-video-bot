import asyncio
import sys
import os

# Add project root to path so we can import src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.comic_migration import migrate_comic_series

if __name__ == "__main__":
    print("Starting Comic Series Migration...")
    try:
        asyncio.run(migrate_comic_series())
        print("Migration completed successfully.")
    except Exception as e:
        print(f"Migration failed: {e}")
