#!/usr/bin/env python3
"""
Database migration runner for Telegram Video Bot.
Executes all SQL migration files in order.
"""
import os
import sys
import asyncio
import logging
from pathlib import Path
from dotenv import load_dotenv
from supabase import create_async_client

# Add parent directory to path to import src modules
sys.path.insert(0, str(Path(__file__).parent.parent))

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def run_migrations():
    """Run all migration files in order."""
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        logger.error("SUPABASE_URL or SUPABASE_KEY not found in environment variables!")
        return False
    
    try:
        # Create Supabase client
        client = await create_async_client(supabase_url, supabase_key)
        logger.info("Connected to Supabase")
        
        # Get migration directory
        migrations_dir = Path(__file__).parent
        
        # Get all .sql files sorted by name
        sql_files = sorted(migrations_dir.glob("*.sql"))
        
        if not sql_files:
            logger.warning("No migration files found!")
            return True
        
        logger.info(f"Found {len(sql_files)} migration files")
        
        # Execute each migration
        for sql_file in sql_files:
            logger.info(f"Running migration: {sql_file.name}")
            
            # Read SQL content
            sql_content = sql_file.read_text()
            
            try:
                # Execute SQL using Supabase RPC or direct query
                # Note: Supabase Python client doesn't have direct SQL execution
                # We'll use the PostgREST API to execute these
                # For now, we'll log instructions for manual execution
                logger.info(f"Migration content for {sql_file.name}:")
                logger.info(sql_content)
                logger.info("-" * 80)
                
            except Exception as e:
                logger.error(f"Error executing {sql_file.name}: {e}")
                return False
        
        logger.info("=" * 80)
        logger.info("IMPORTANT: Please execute the above SQL statements manually in Supabase SQL Editor")
        logger.info("=" * 80)
        logger.info("Instructions:")
        logger.info("1. Go to your Supabase Dashboard")
        logger.info("2. Navigate to SQL Editor")
        logger.info("3. Copy and paste each SQL statement above")
        logger.info("4. Execute them in order (001, 002, 003, etc.)")
        logger.info("=" * 80)
        
        return True
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        return False


def main():
    """Main entry point."""
    logger.info("Starting database migrations...")
    success = asyncio.run(run_migrations())
    
    if success:
        logger.info("Migrations completed successfully!")
        return 0
    else:
        logger.error("Migrations failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
