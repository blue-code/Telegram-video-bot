import logging
import asyncio
from src import db
from src.series_parser import extract_series_info

logger = logging.getLogger(__name__)

async def migrate_epub_series(user_id: int = None):
    """
    Scans all EPUB files in the database and updates their series metadata
    based on the filename regex patterns.
    """
    logger.info("Starting EPUB series migration...")
    
    offset = 0
    limit = 50
    total_processed = 0
    
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
            if ext != 'epub':
                continue
                
            # Process EPUB
            file_id = file_record["id"]
            
            # Extract series info purely from filename
            series, volume = extract_series_info(file_name)
            
            if series:
                # Update metadata
                metadata = file_record.get("metadata") or {}
                
                # Only update if changed or missing
                old_series = metadata.get("series")
                old_volume = metadata.get("volume")
                
                if old_series != series or old_volume != volume:
                    metadata["series"] = series
                    metadata["volume"] = volume
                    
                    # Update DB
                    sb = await db.get_database()
                    await sb.table("files").update({"metadata": metadata}).eq("id", file_id).execute()
                    
                    logger.info(f"Updated EPUB: {file_name} -> Series: {series}, Vol: {volume}")
                    total_processed += 1
            
        offset += limit
        
    logger.info(f"EPUB series migration complete. Updated {total_processed} files.")
    return total_processed

if __name__ == "__main__":
    asyncio.run(migrate_epub_series())
