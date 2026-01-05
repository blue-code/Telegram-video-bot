"""
Link shortener module for generating short unique IDs for video sharing.
"""
import string
import random
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def generate_short_id(length: int = 8) -> str:
    """
    Generate a random short ID for URL shortening.
    
    Args:
        length: Length of the short ID (default: 8 characters)
        
    Returns:
        A random alphanumeric string
    """
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))


async def create_short_link(db_client, file_id: str, video_id: Optional[int], user_id: int) -> str:
    """
    Create a short link for a file_id and store it in the database.
    
    Args:
        db_client: Supabase async client
        file_id: Telegram file ID
        video_id: Video ID in database (optional)
        user_id: Telegram user ID
        
    Returns:
        The generated short_id
    """
    max_attempts = 5
    
    for attempt in range(max_attempts):
        short_id = generate_short_id()
        
        try:
            # Try to insert the short link
            result = await db_client.table("shared_links").insert({
                "short_id": short_id,
                "file_id": file_id,
                "video_id": video_id,
                "user_id": user_id,
                "views": 0
            }).execute()
            
            logger.info(f"Created short link: {short_id} -> {file_id}")
            return short_id
            
        except Exception as e:
            # If collision (unlikely), try again
            if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                logger.warning(f"Short ID collision on attempt {attempt + 1}, retrying...")
                continue
            else:
                logger.error(f"Error creating short link: {e}")
                raise
    
    # If all attempts failed
    raise Exception("Failed to generate unique short ID after maximum attempts")


async def resolve_short_link(db_client, short_id: str) -> Optional[dict]:
    """
    Resolve a short_id to its file_id and metadata.
    
    Args:
        db_client: Supabase async client
        short_id: The short ID to resolve
        
    Returns:
        Dictionary with file_id and metadata, or None if not found
    """
    try:
        result = await db_client.table("shared_links").select("*").eq("short_id", short_id).execute()
        
        if result.data:
            # Increment view count
            link_data = result.data[0]
            await db_client.table("shared_links").update({
                "views": link_data.get("views", 0) + 1
            }).eq("short_id", short_id).execute()
            
            return link_data
        
        return None
        
    except Exception as e:
        logger.error(f"Error resolving short link {short_id}: {e}")
        return None


async def get_or_create_short_link(db_client, file_id: str, video_id: Optional[int], user_id: int) -> str:
    """
    Get existing short link for a file_id or create a new one.
    
    Args:
        db_client: Supabase async client
        file_id: Telegram file ID
        video_id: Video ID in database (optional)
        user_id: Telegram user ID
        
    Returns:
        The short_id (existing or newly created)
    """
    try:
        # Check if short link already exists for this file_id
        result = await db_client.table("shared_links").select("short_id").eq("file_id", file_id).execute()
        
        if result.data:
            return result.data[0]["short_id"]
        
        # Create new short link
        return await create_short_link(db_client, file_id, video_id, user_id)
        
    except Exception as e:
        logger.error(f"Error in get_or_create_short_link: {e}")
        # Return file_id as fallback
        return file_id
