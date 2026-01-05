import os
from supabase import create_async_client, AsyncClient
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
VIDEO_TABLE = "videos"

client: AsyncClient = None

async def get_database() -> AsyncClient:
    """Returns the Supabase async client instance."""
    global client
    if client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("SUPABASE_URL or SUPABASE_KEY not found in environment variables!")
        client = await create_async_client(SUPABASE_URL, SUPABASE_KEY)
    return client

async def close_database():
    """No explicit close needed for Supabase client, but kept for interface compatibility."""
    global client
    client = None

async def save_video_metadata(data: dict):
    """
    Saves video metadata to Supabase.
    If the URL already exists, it will be updated (upsert).
    """
    sb = await get_database()
    result = await sb.table(VIDEO_TABLE).upsert(data, on_conflict="url").execute()
    return result.data

async def get_video_by_url(url: str):
    """Retrieves video metadata by original URL."""
    sb = await get_database()
    result = await sb.table(VIDEO_TABLE).select("*").eq("url", url).execute()
    return result.data[0] if result.data else None

async def get_video_by_file_id(file_id: str):
    """Retrieves video metadata by Telegram File ID."""
    sb = await get_database()
    result = await sb.table(VIDEO_TABLE).select("*").eq("file_id", file_id).execute()
    return result.data[0] if result.data else None


async def get_user_videos(user_id: int, limit: int = 10, offset: int = 0):
    """
    Get videos for a specific user with pagination.
    
    Args:
        user_id: Telegram user ID
        limit: Number of videos to return
        offset: Offset for pagination
        
    Returns:
        List of video metadata
    """
    sb = await get_database()
    result = await sb.table(VIDEO_TABLE).select("*").eq("user_id", user_id).order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    return result.data if result.data else []


async def search_user_videos(user_id: int, keyword: str, limit: int = 10):
    """
    Search videos by title for a specific user.
    
    Args:
        user_id: Telegram user ID
        keyword: Search keyword
        limit: Number of videos to return
        
    Returns:
        List of matching video metadata
    """
    sb = await get_database()
    result = await sb.table(VIDEO_TABLE).select("*").eq("user_id", user_id).ilike("title", f"%{keyword}%").order("created_at", desc=True).limit(limit).execute()
    return result.data if result.data else []


async def get_recent_videos(user_id: int, limit: int = 5):
    """
    Get most recent videos for a user.
    
    Args:
        user_id: Telegram user ID
        limit: Number of videos to return
        
    Returns:
        List of recent video metadata
    """
    sb = await get_database()
    result = await sb.table(VIDEO_TABLE).select("*").eq("user_id", user_id).order("created_at", desc=True).limit(limit).execute()
    return result.data if result.data else []


async def add_favorite(user_id: int, video_id: int):
    """
    Add a video to user's favorites.
    
    Args:
        user_id: Telegram user ID
        video_id: Video ID
        
    Returns:
        True if successful, False otherwise
    """
    try:
        sb = await get_database()
        await sb.table("favorites").insert({
            "user_id": user_id,
            "video_id": video_id
        }).execute()
        return True
    except Exception:
        return False


async def remove_favorite(user_id: int, video_id: int):
    """
    Remove a video from user's favorites.
    
    Args:
        user_id: Telegram user ID
        video_id: Video ID
        
    Returns:
        True if successful, False otherwise
    """
    try:
        sb = await get_database()
        await sb.table("favorites").delete().eq("user_id", user_id).eq("video_id", video_id).execute()
        return True
    except Exception:
        return False


async def is_favorite(user_id: int, video_id: int):
    """
    Check if a video is in user's favorites.
    
    Args:
        user_id: Telegram user ID
        video_id: Video ID
        
    Returns:
        True if favorite, False otherwise
    """
    try:
        sb = await get_database()
        result = await sb.table("favorites").select("id").eq("user_id", user_id).eq("video_id", video_id).execute()
        return bool(result.data)
    except Exception:
        return False


async def get_user_favorites(user_id: int, limit: int = 10, offset: int = 0):
    """
    Get user's favorite videos with pagination.
    
    Args:
        user_id: Telegram user ID
        limit: Number of videos to return
        offset: Offset for pagination
        
    Returns:
        List of favorite video metadata
    """
    sb = await get_database()
    # Join favorites with videos table
    result = await sb.table("favorites").select("video_id, videos(*)").eq("user_id", user_id).order("created_at", desc=True).range(offset, offset + limit - 1).execute()
    
    if result.data:
        # Extract video data from join
        return [item.get("videos") for item in result.data if item.get("videos")]
    return []


async def get_video_by_id(video_id: int):
    """
    Get video by ID.
    
    Args:
        video_id: Video ID
        
    Returns:
        Video metadata or None
    """
    sb = await get_database()
    result = await sb.table(VIDEO_TABLE).select("*").eq("id", video_id).execute()
    return result.data[0] if result.data else None


async def delete_video(video_id: int, user_id: int):
    """
    Delete a video (only if it belongs to the user).
    
    Args:
        video_id: Video ID
        user_id: Telegram user ID
        
    Returns:
        True if deleted, False otherwise
    """
    try:
        sb = await get_database()
        await sb.table(VIDEO_TABLE).delete().eq("id", video_id).eq("user_id", user_id).execute()
        return True
    except Exception:
        return False


async def increment_view_count(video_id: int):
    """
    Increment view count for a video.
    
    Args:
        video_id: Video ID
    """
    try:
        sb = await get_database()
        # Get current views
        result = await sb.table(VIDEO_TABLE).select("views").eq("id", video_id).execute()
        if result.data:
            current_views = result.data[0].get("views", 0) or 0
            await sb.table(VIDEO_TABLE).update({
                "views": current_views + 1,
                "last_viewed": "now()"
            }).eq("id", video_id).execute()
    except Exception as e:
        import logging
        logging.error(f"Error incrementing view count: {e}")


async def get_popular_videos(limit: int = 10):
    """
    Get most popular videos across all users.
    
    Args:
        limit: Number of videos to return
        
    Returns:
        List of popular video metadata
    """
    sb = await get_database()
    result = await sb.table(VIDEO_TABLE).select("*").order("views", desc=True).limit(limit).execute()
    return result.data if result.data else []


async def get_video_count(user_id: int = None):
    """
    Get total video count for a user or all users.
    
    Args:
        user_id: Telegram user ID (optional)
        
    Returns:
        Video count
    """
    sb = await get_database()
    query = sb.table(VIDEO_TABLE).select("id", count="exact")
    
    if user_id:
        query = query.eq("user_id", user_id)
    
    result = await query.execute()
    return result.count if hasattr(result, 'count') else 0
