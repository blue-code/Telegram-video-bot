import logging
import asyncio
from src import db, comic_parser

logger = logging.getLogger(__name__)

async def migrate_comic_series(user_id: int = None):
    """
    Scans all comic files in the database and updates their series metadata
    based on the latest regex patterns.
    """
    logger.info("Starting comic series migration...")
    
    offset = 0
    limit = 50
    total_processed = 0
    
    # Use Super Admin ID if no user specified to attempt to cover all files
    # Note: get_files logic filters by user_id unless super admin.
    target_user_id = user_id if user_id else db.SUPER_ADMIN_ID
    
    while True:
        # Fetch files from the 'files' table
        files = await db.get_files(
            user_id=target_user_id, 
            limit=limit, 
            offset=offset,
            sort_by="latest"
        )
        
        if not files:
            break
            
        for file_record in files:
            file_name = file_record.get("file_name", "")
            if not file_name:
                continue
                
            # Check extension (case-insensitive)
            ext = file_name.split('.')[-1].lower() if '.' in file_name else ''
            if ext not in ['zip', 'cbz']:
                continue
                
            # Process comic
            file_id = file_record["id"]
            
            # Extract series info purely from filename
            # We don't need local file access for this part
            series, volume = comic_parser.extract_series_info(file_name)
            
            # Determine title
            if volume:
                title = f"{series} {volume}권"
            else:
                title = series
            
            # Fetch existing comic record to preserve other metadata
            existing_comic = await db.get_comic_by_file_id(file_id)
            
            comic_data = {
                "file_id": file_id,
                "user_id": file_record["user_id"],
                "title": title,
                "series": series,
                "volume": volume,
                # Preserve existing data if available, else defaults
                "page_count": existing_comic["page_count"] if existing_comic else 0,
                "folder": existing_comic["folder"] if existing_comic else None,
                "cover_url": existing_comic["cover_url"] if existing_comic else None,
                "metadata": existing_comic["metadata"] if existing_comic else {}
            }
            
            # Upsert into comics table
            await db.save_comic_metadata(comic_data)
            total_processed += 1
            
        offset += limit
        
    logger.info(f"Comic series migration complete. Processed {total_processed} comics.")
    return total_processed

if __name__ == "__main__":
    # Allow running as a script for testing
    asyncio.run(migrate_comic_series())
