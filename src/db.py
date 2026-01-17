import os
from supabase import create_async_client, AsyncClient
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
VIDEO_TABLE = "videos"
FILES_TABLE = "files"
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "41509535"))

client: AsyncClient = None

# ... (existing functions) ...

async def get_files(
    user_id: int, 
    limit: int = 20, 
    offset: int = 0,
    query: str = None,
    date_from: str = None,
    date_to: str = None,
    sort_by: str = "latest",
    ext: str = None
):
    """
    Get generic files for a user with filtering and sorting.
    """
    sb = await get_database()
    q = sb.table(FILES_TABLE).select("*")
    
    if not _is_super_admin(user_id):
        q = q.eq("user_id", user_id)
    
    # Text search (file_name OR metadata->author OR metadata->book_title)
    if query:
        # Construct OR filter for PostgREST
        search_filter = f"file_name.ilike.%{query}%,metadata->>author.ilike.%{query}%,metadata->>book_title.ilike.%{query}%"
        q = q.or_(search_filter)
    
    # Extension filter - Disabled due to Cloudflare 500 error
    # if ext:
    #    if ext == "epub":
    #        q = q.like("file_name", "%.epub")
        # Add more extensions here if needed
    
    # Date range filter
    if date_from:
        q = q.gte("created_at", date_from)
    if date_to:
        q = q.lte("created_at", date_to)
    
    # Sorting
    if sort_by == "latest":
        q = q.order("created_at", desc=True)
    elif sort_by == "oldest":
        q = q.order("created_at", desc=False)
    elif sort_by == "name_asc":
        q = q.order("file_name", desc=False)
    elif sort_by == "name_desc":
        q = q.order("file_name", desc=True)
    elif sort_by == "size_desc":
        q = q.order("file_size", desc=True)
    elif sort_by == "size_asc":
        q = q.order("file_size", desc=False)
    else:
        q = q.order("created_at", desc=True)
    
    q = q.range(offset, offset + limit - 1)
    result = await q.execute()
    return result.data if result.data else []

async def save_reading_progress(user_id: int, file_id: int, cfi: str, percent: float):
    """Save or update reading progress."""
    import logging
    logger = logging.getLogger(__name__)

    sb = await get_database()

    # Check if exists
    existing = await sb.table("reading_progress").select("id").eq("user_id", user_id).eq("file_id", file_id).execute()

    data = {
        "user_id": user_id,
        "file_id": file_id,
        "cfi": cfi,
        "percent": percent,
        "updated_at": "now()"
    }

    if existing.data:
        # Update
        logger.info(f"💾 Updating reading progress: user={user_id}, file={file_id}, percent={percent:.1f}%, CFI={cfi[:50]}...")
        await sb.table("reading_progress").update(data).eq("id", existing.data[0]['id']).execute()
    else:
        # Insert
        logger.info(f"💾 Inserting reading progress: user={user_id}, file={file_id}, percent={percent:.1f}%, CFI={cfi[:50]}...")
        await sb.table("reading_progress").insert(data).execute()
    return True

async def get_reading_progress(user_id: int, file_id: int):
    """Get reading progress for a specific file."""
    import logging
    logger = logging.getLogger(__name__)

    sb = await get_database()
    result = await sb.table("reading_progress").select("*").eq("user_id", user_id).eq("file_id", file_id).execute()

    if result.data:
        progress = result.data[0]
        logger.info(f"📖 Loading reading progress: user={user_id}, file={file_id}, percent={progress.get('percent', 0):.1f}%, CFI={progress.get('cfi', '')[:50]}...")
        return progress
    else:
        logger.info(f"📖 No reading progress found: user={user_id}, file={file_id}")
        return None

async def get_recent_reading(user_id: int):
    """Get the most recently read book."""
    sb = await get_database()
    # Join with files table to get file details
    result = await sb.table("reading_progress").select("*, files(*)").eq("user_id", user_id).order("updated_at", desc=True).limit(1).execute()
    if result.data and result.data[0].get('files'):
        return result.data[0]
    return None

async def add_file(file_data: dict):
    """
    Add a new file record.
    """
    sb = await get_database()
    result = await sb.table(FILES_TABLE).insert(file_data).execute()
    return result.data[0] if result.data else None

async def delete_file(file_id: int, user_id: int):
    """
    Delete a file record.
    """
    sb = await get_database()
    query = sb.table(FILES_TABLE).delete().eq("id", file_id)
    if not _is_super_admin(user_id):
        query = query.eq("user_id", user_id)
    
    result = await query.execute()
    return bool(result.data)

async def get_file_by_id(file_id: int):
    """
    Get file metadata by ID.
    """
    sb = await get_database()
    result = await sb.table(FILES_TABLE).select("*").eq("id", file_id).execute()
    return result.data[0] if result.data else None

async def search_files(user_id: int, query: str, limit: int = 20):
    """
    Search files by name.
    """
    sb = await get_database()
    q = sb.table(FILES_TABLE).select("*").ilike("file_name", f"%{query}%")
    if not _is_super_admin(user_id):
        q = q.eq("user_id", user_id)
    
    result = await q.order("created_at", desc=True).limit(limit).execute()
    return result.data if result.data else []

async def count_files(
    user_id: int,
    query: str = None,
    date_from: str = None,
    date_to: str = None,
    ext: str = None
):
    """
    Count files matching criteria.
    """
    sb = await get_database()
    q = sb.table(FILES_TABLE).select("id", count="exact")
    
    if not _is_super_admin(user_id):
        q = q.eq("user_id", user_id)
    
    if query:
        # Same OR filter as get_files
        search_filter = f"file_name.ilike.%{query}%,metadata->>author.ilike.%{query}%,metadata->>book_title.ilike.%{query}%"
        q = q.or_(search_filter)
        
    if date_from:
        q = q.gte("created_at", date_from)
    if date_to:
        q = q.lte("created_at", date_to)
        
    # Extension filter - Disabled due to Cloudflare 500 error
    # if ext:
    #    if ext == "epub":
    #        q = q.like("file_name", "%.epub")
        
    result = await q.execute()
    return result.count if hasattr(result, 'count') else 0

def _filter_master_videos(videos: list[dict]) -> list[dict]:
    """Filter out split part records (keep master or single entries)."""
    filtered = []
    for video in videos:
        metadata = video.get("metadata") or {}
        part_index = metadata.get("part_index")
        if part_index is None:
            filtered.append(video)
            continue
        try:
            part_index_value = int(part_index)
        except (TypeError, ValueError):
            filtered.append(video)
            continue
        if part_index_value <= 1:
            filtered.append(video)
    return filtered

def _is_super_admin(user_id: int) -> bool:
    return user_id == SUPER_ADMIN_ID

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

    # Check if video with this URL already exists
    existing = await get_video_by_url(data.get("url"))

    if existing:
        # Update existing record
        result = await sb.table(VIDEO_TABLE).update(data).eq("id", existing["id"]).execute()
    else:
        # Insert new record
        result = await sb.table(VIDEO_TABLE).insert(data).execute()

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


async def get_user_videos(user_id: int, filter: str = "all", search: str = "", limit: int = 20, offset: int = 0):
    """
    Get videos for a specific user with filtering and search.
    
    Args:
        user_id: Telegram user ID
        filter: Filter type ('all', 'favorites', 'recent')
        search: Search keyword for title
        limit: Number of videos to return
        offset: Offset for pagination
        
    Returns:
        List of video metadata
    """
    sb = await get_database()
    
    if filter == "favorites":
        # Get favorite videos
        result = await sb.table("favorites").select("video_id, videos(*)").eq("user_id", user_id).order("created_at", desc=True).range(offset, offset + limit - 1).execute()
        
        if result.data:
            videos = [item.get("videos") for item in result.data if item.get("videos")]
            
            # Apply search filter if provided
            if search:
                videos = [v for v in videos if search.lower() in v.get('title', '').lower()]

            return _filter_master_videos(videos)
        return []
    
    # Regular video query
    query = sb.table(VIDEO_TABLE).select("*")
    if not _is_super_admin(user_id):
        query = query.eq("user_id", user_id)
    
    # Apply search filter
    if search:
        query = query.ilike("title", f"%{search}%")
    
    # Apply sorting
    query = query.order("created_at", desc=True)
    
    # Apply pagination
    result = await query.range(offset, offset + limit - 1).execute()
    
    videos = result.data if result.data else []
    return _filter_master_videos(videos)


async def get_encoded_videos(user_id: int, limit: int = 20, offset: int = 0):
    """
    Get videos that have been encoded/optimized for mobile.
    
    Args:
        user_id: Telegram user ID
        limit: Number of videos to return
        offset: Offset for pagination
        
    Returns:
        List of encoded video metadata
    """
    sb = await get_database()
    
    # Supabase JSONB filtering syntax: metadata->>'is_encoded' eq 'true'
    # Note: Depending on how boolean is stored in JSONB, it might be true (bool) or 'true' (string)
    # The transcoder sets it as boolean True.
    # In PostgREST/Supabase, we can use `is` filter on JSON path or `eq`.
    # Let's try matching the JSON structure.
    
    query = sb.table(VIDEO_TABLE).select("*")
    if not _is_super_admin(user_id):
        query = query.eq("user_id", user_id)
    
    # Filter for is_encoded: true in metadata
    # The arrow operator ->> returns text, so 'true'
    query = query.eq("metadata->>is_encoded", "true")
    
    query = query.order("created_at", desc=True).range(offset, offset + limit - 1)
    
    result = await query.execute()
    
    videos = result.data if result.data else []
    return _filter_master_videos(videos)


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
    query = sb.table(VIDEO_TABLE).select("*").ilike("title", f"%{keyword}%")
    if not _is_super_admin(user_id):
        query = query.eq("user_id", user_id)
    result = await query.order("created_at", desc=True).limit(limit).execute()
    videos = result.data if result.data else []
    return _filter_master_videos(videos)


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
    query = sb.table(VIDEO_TABLE).select("*")
    if not _is_super_admin(user_id):
        query = query.eq("user_id", user_id)
    result = await query.order("created_at", desc=True).limit(limit).execute()
    videos = result.data if result.data else []
    return _filter_master_videos(videos)


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
        videos = [item.get("videos") for item in result.data if item.get("videos")]
        return _filter_master_videos(videos)
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
        Tuple (success, message)
    """
    try:
        sb = await get_database()

        lookup = sb.table(VIDEO_TABLE).select("id")
        if not _is_super_admin(user_id):
            lookup = lookup.eq("user_id", user_id)
        lookup = lookup.eq("id", video_id)
        existing = await lookup.execute()
        if not existing.data:
            return False, "Video not found or unauthorized"

        short_ids = []
        try:
            links = await sb.table("shared_links").select("short_id").eq("video_id", video_id).execute()
            short_ids = [item.get("short_id") for item in (links.data or []) if item.get("short_id")]
        except Exception:
            short_ids = []

        if short_ids:
            try:
                await sb.table("views").delete().in_("short_id", short_ids).execute()
            except Exception:
                pass

        try:
            await sb.table("favorites").delete().eq("video_id", video_id).execute()
        except Exception:
            pass

        try:
            await sb.table("shared_links").delete().eq("video_id", video_id).execute()
        except Exception:
            pass

        query = sb.table(VIDEO_TABLE).delete().eq("id", video_id)
        if not _is_super_admin(user_id):
            query = query.eq("user_id", user_id)
        result = await query.execute()
        deleted = bool(result.data)
        if not deleted:
            return False, "Delete failed"
        return True, "Video deleted"
    except Exception as error:
        return False, str(error)


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
    videos = result.data if result.data else []
    return _filter_master_videos(videos)


async def get_video_count(user_id: int = None, filter: str = "all"):
    """
    Get total video count for a user or all users.
    
    Args:
        user_id: Telegram user ID (optional)
        filter: Filter type ('all', 'favorites', 'recent')
        
    Returns:
        Video count
    """
    sb = await get_database()
    
    if filter == "favorites" and user_id:
        # Count favorites
        result = await sb.table("favorites").select("id", count="exact").eq("user_id", user_id).execute()
        return result.count if hasattr(result, 'count') else 0
    
    query = sb.table(VIDEO_TABLE).select("id", count="exact")
    
    if user_id and not _is_super_admin(user_id):
        query = query.eq("user_id", user_id)
    
    result = await query.execute()
    return result.count if hasattr(result, 'count') else 0


async def get_video_by_short_id(short_id: str):
    """
    Get video info by short_id from shared_links table.
    
    Args:
        short_id: Short ID from shared link
        
    Returns:
        Video data with views count or None
    """
    try:
        sb = await get_database()
        
        # Get shared link data
        link_result = await sb.table("shared_links").select("*").eq("short_id", short_id).execute()
        
        if not link_result.data:
            return None
        
        link_data = link_result.data[0]
        video_id = link_data.get("video_id")
        file_id = link_data.get("file_id")
        
        # Get video metadata if video_id exists
        video_data = None
        if video_id:
            video_result = await sb.table(VIDEO_TABLE).select("*").eq("id", video_id).execute()
            if video_result.data:
                video_data = video_result.data[0]
        
        # If no video metadata, try to get by file_id
        if not video_data and file_id:
            video_result = await sb.table(VIDEO_TABLE).select("*").eq("file_id", file_id).execute()
            if video_result.data:
                video_data = video_result.data[0]
        
        # Combine link data with video data
        if video_data:
            video_data['views'] = link_data.get('views', 0)
            video_data['short_id'] = short_id
            return video_data
        
        # Return just link data if no video metadata found
        return {
            'file_id': file_id,
            'short_id': short_id,
            'views': link_data.get('views', 0),
            'title': 'Unknown',
            'duration': 0,
            'created_at': link_data.get('created_at')
        }
        
    except Exception as e:
        import logging
        logging.error(f"Error getting video by short_id: {e}")
        return None


async def increment_view_count_by_short_id(short_id: str, ip_address: str = None, user_agent: str = None):
    """
    Increment view count for a video by short_id.
    
    Args:
        short_id: Short ID from shared link
        ip_address: Optional IP address of viewer
        user_agent: Optional user agent string
    """
    try:
        sb = await get_database()
        
        # Get current views from shared_links
        result = await sb.table("shared_links").select("views, video_id").eq("short_id", short_id).execute()
        
        if result.data:
            current_views = result.data[0].get("views", 0) or 0
            video_id = result.data[0].get("video_id")
            
            # Update views in shared_links
            await sb.table("shared_links").update({
                "views": current_views + 1
            }).eq("short_id", short_id).execute()
            
            # Also update video table if video_id exists
            if video_id:
                video_result = await sb.table(VIDEO_TABLE).select("views").eq("id", video_id).execute()
                if video_result.data:
                    video_views = video_result.data[0].get("views", 0) or 0
                    await sb.table(VIDEO_TABLE).update({
                        "views": video_views + 1,
                        "last_viewed": "now()"
                    }).eq("id", video_id).execute()
            
            # Insert into views table for analytics (if it exists)
            try:
                await sb.table("views").insert({
                    "short_id": short_id,
                    "user_id": None,  # Web viewer, not Telegram user
                    "ip_address": ip_address,
                    "user_agent": user_agent
                }).execute()
            except Exception:
                pass  # views table might not exist yet
                
    except Exception as e:
        import logging
        logging.error(f"Error incrementing view count: {e}")


async def delete_video_by_id(video_id: int, user_id: int):
    """
    Delete a video by ID (only if it belongs to the user).
    Alias for delete_video for consistency.
    
    Args:
        video_id: Video ID
        user_id: Telegram user ID
        
    Returns:
        Tuple (success, message)
    """
    return await delete_video(video_id, user_id)


async def get_favorite_videos(user_id: int):
    """
    Get user's favorite videos.
    Alias for get_user_favorites for consistency.
    
    Args:
        user_id: Telegram user ID
        
    Returns:
        List of favorite video metadata
    """
    return await get_user_favorites(user_id, limit=100, offset=0)


async def search_videos(
    user_id: int,
    query: str = "",
    date_from: str = "",
    date_to: str = "",
    duration_filter: str = "all",
    sort_by: str = "latest",
    limit: int = 100
):
    """Advanced search with filters"""
    sb = await get_database()
    
    # Build query
    q = sb.table(VIDEO_TABLE).select("*")
    if not _is_super_admin(user_id):
        q = q.eq("user_id", user_id)
    
    # Text search
    if query:
        q = q.ilike("title", f"%{query}%")
    
    # Date range filter
    if date_from:
        q = q.gte("created_at", date_from)
    if date_to:
        q = q.lte("created_at", date_to)
    
    # Duration filter
    if duration_filter == "short":
        q = q.lt("duration", 300)  # < 5 min
    elif duration_filter == "medium":
        q = q.gte("duration", 300).lte("duration", 1200)  # 5-20 min
    elif duration_filter == "long":
        q = q.gt("duration", 1200)  # > 20 min
    
    # Sorting
    if sort_by == "latest":
        q = q.order("created_at", desc=True)
    elif sort_by == "views":
        q = q.order("views", desc=True)
    elif sort_by == "title":
        q = q.order("title", desc=False)
    elif sort_by == "duration":
        q = q.order("duration", desc=True)
    
    q = q.limit(limit)
    result = await q.execute()
    
    videos = result.data if result.data else []
    return _filter_master_videos(videos)


async def update_video_metadata(
    video_id: int,
    user_id: int,
    title: str = None,
    description: str = None,
    tags: list = None
):
    """Update video metadata"""
    sb = await get_database()

    update_data = {}
    if title:
        update_data['title'] = title
    if description:
        update_data['description'] = description
    if tags is not None:
        update_data['tags'] = tags

    result = await sb.table(VIDEO_TABLE).update(update_data).eq("id", video_id).eq("user_id", user_id).execute()

    return len(result.data) > 0


# ============== COMIC BOOK FUNCTIONS ==============

async def save_comic_metadata(comic_data: dict):
    """
    Save comic book metadata to database.

    Args:
        comic_data: Dictionary containing comic metadata
            - file_id: int (reference to files table)
            - user_id: int
            - title: str
            - series: str
            - volume: int
            - folder: str
            - page_count: int
            - cover_url: str (optional)
            - metadata: dict (additional data like cover_bytes)

    Returns:
        Saved comic record or None
    """
    sb = await get_database()

    # Check if comic already exists for this file_id
    existing = await sb.table("comics").select("id").eq("file_id", comic_data.get("file_id")).execute()

    if existing.data:
        # Update existing record
        result = await sb.table("comics").update(comic_data).eq("id", existing.data[0]["id"]).execute()
    else:
        # Insert new record
        result = await sb.table("comics").insert(comic_data).execute()

    return result.data[0] if result.data else None


async def get_comic_by_file_id(file_id: int):
    """
    Get comic metadata by file ID.

    Args:
        file_id: File ID from files table

    Returns:
        Comic metadata or None
    """
    sb = await get_database()
    result = await sb.table("comics").select("*").eq("file_id", file_id).execute()
    return result.data[0] if result.data else None


async def get_comics(
    user_id: int,
    limit: int = 24,
    offset: int = 0,
    query: str = None,
    series: str = None,
    sort_by: str = "latest"
):
    """
    Get comics for a user with filtering and sorting.

    Args:
        user_id: User ID
        limit: Number of comics to return
        offset: Offset for pagination
        query: Search query (title or series)
        series: Filter by specific series
        sort_by: Sort order ('latest', 'oldest', 'title', 'series', 'volume')

    Returns:
        List of comic metadata with file info
    """
    sb = await get_database()

    # Join comics with files table
    q = sb.table("comics").select("*, files(*)")

    if not _is_super_admin(user_id):
        q = q.eq("user_id", user_id)

    # Search filter
    if query:
        # Search in title or series
        q = q.or_(f"title.ilike.%{query}%,series.ilike.%{query}%")

    # Series filter
    if series:
        q = q.eq("series", series)

    # Sorting
    if sort_by == "latest":
        q = q.order("created_at", desc=True)
    elif sort_by == "oldest":
        q = q.order("created_at", desc=False)
    elif sort_by == "title":
        q = q.order("title", desc=False)
    elif sort_by == "series":
        q = q.order("series", desc=False).order("volume", desc=False)
    elif sort_by == "volume":
        q = q.order("volume", desc=False)
    else:
        q = q.order("created_at", desc=True)

    q = q.range(offset, offset + limit - 1)
    result = await q.execute()

    return result.data if result.data else []


async def count_comics(
    user_id: int,
    query: str = None,
    series: str = None
):
    """
    Count comics matching criteria.

    Args:
        user_id: User ID
        query: Search query
        series: Filter by series

    Returns:
        Comic count
    """
    sb = await get_database()
    q = sb.table("comics").select("id", count="exact")

    if not _is_super_admin(user_id):
        q = q.eq("user_id", user_id)

    if query:
        q = q.or_(f"title.ilike.%{query}%,series.ilike.%{query}%")

    if series:
        q = q.eq("series", series)

    result = await q.execute()
    return result.count if hasattr(result, 'count') else 0


async def get_comic_series(user_id: int):
    """
    Get list of all comic series for a user with volume count.

    Args:
        user_id: User ID

    Returns:
        List of series with metadata
    """
    sb = await get_database()

    # Get all comics for user
    q = sb.table("comics").select("series, title, file_id, created_at, metadata")

    if not _is_super_admin(user_id):
        q = q.eq("user_id", user_id)

    result = await q.order("series", desc=False).order("volume", desc=False).execute()

    if not result.data:
        return []

    # Group by series
    series_map = {}
    for comic in result.data:
        series_name = comic.get("series") or comic.get("title") or "Unknown"

        if series_name not in series_map:
            series_map[series_name] = {
                "series": series_name,
                "volume_count": 0,
                "first_file_id": comic.get("file_id"),
                "latest_update": comic.get("created_at"),
                "cover_url": None
            }

        series_map[series_name]["volume_count"] += 1

        # Update latest update time
        if comic.get("created_at") and comic["created_at"] > series_map[series_name]["latest_update"]:
            series_map[series_name]["latest_update"] = comic["created_at"]

    return list(series_map.values())


async def get_comics_by_series(
    user_id: int,
    series_name: str,
    limit: int = 100,
    offset: int = 0
):
    """
    Get all comics in a specific series.

    Args:
        user_id: User ID
        series_name: Series name
        limit: Number of comics to return
        offset: Offset for pagination

    Returns:
        List of comics in the series
    """
    sb = await get_database()

    q = sb.table("comics").select("*, files(*)").eq("series", series_name)

    if not _is_super_admin(user_id):
        q = q.eq("user_id", user_id)

    # Sort by volume number
    q = q.order("volume", desc=False).order("title", desc=False)
    q = q.range(offset, offset + limit - 1)

    result = await q.execute()
    return result.data if result.data else []


async def save_comic_progress(
    user_id: int,
    file_id: int,
    current_page: int,
    settings: dict = None
):
    """
    Save or update comic reading progress.

    Args:
        user_id: User ID
        file_id: File ID
        current_page: Current page number
        settings: Reading settings (reading_direction, mode)

    Returns:
        True if successful
    """
    import logging
    logger = logging.getLogger(__name__)

    sb = await get_database()

    # Check if exists
    existing = await sb.table("comic_progress").select("id").eq("user_id", user_id).eq("file_id", file_id).execute()

    data = {
        "user_id": user_id,
        "file_id": file_id,
        "current_page": current_page,
        "updated_at": "now()"
    }

    if settings:
        data["settings"] = settings

    if existing.data:
        # Update
        logger.info(f"💾 Updating comic progress: user={user_id}, file={file_id}, page={current_page}")
        await sb.table("comic_progress").update(data).eq("id", existing.data[0]['id']).execute()
    else:
        # Insert
        logger.info(f"💾 Inserting comic progress: user={user_id}, file={file_id}, page={current_page}")
        await sb.table("comic_progress").insert(data).execute()

    return True


async def get_comic_progress(user_id: int, file_id: int):
    """
    Get reading progress for a specific comic.

    Args:
        user_id: User ID
        file_id: File ID

    Returns:
        Progress data or None
    """
    import logging
    logger = logging.getLogger(__name__)

    sb = await get_database()
    result = await sb.table("comic_progress").select("*").eq("user_id", user_id).eq("file_id", file_id).execute()

    if result.data:
        progress = result.data[0]
        logger.info(f"📖 Loading comic progress: user={user_id}, file={file_id}, page={progress.get('current_page', 0)}")
        return progress
    else:
        logger.info(f"📖 No comic progress found: user={user_id}, file={file_id}")
        return None


async def get_recent_comic_reading(user_id: int, limit: int = 5):
    """
    Get recently read comics.

    Args:
        user_id: User ID
        limit: Number of comics to return

    Returns:
        List of recently read comics with progress
    """
    sb = await get_database()

    # Join with comics and files table
    result = await sb.table("comic_progress").select("*, comics(*, files(*))").eq("user_id", user_id).order("updated_at", desc=True).limit(limit).execute()

    if result.data:
        return result.data
    return []


async def delete_comic(file_id: int, user_id: int):
    """
    Delete a comic record.

    Args:
        file_id: File ID
        user_id: User ID

    Returns:
        True if successful
    """
    sb = await get_database()

    # Delete comic progress first
    try:
        await sb.table("comic_progress").delete().eq("file_id", file_id).eq("user_id", user_id).execute()
    except Exception:
        pass

    # Delete comic metadata
    query = sb.table("comics").delete().eq("file_id", file_id)

    if not _is_super_admin(user_id):
        query = query.eq("user_id", user_id)

    result = await query.execute()
    return bool(result.data)


async def add_comic_favorite(user_id: int, file_id: int):
    """
    Add comic to user's favorites.

    Args:
        user_id: User ID
        file_id: File ID

    Returns:
        True if successful
    """
    try:
        sb = await get_database()
        await sb.table("comic_favorites").insert({
            "user_id": user_id,
            "file_id": file_id
        }).execute()
        return True
    except Exception:
        # Might already exist (unique constraint)
        return False


async def remove_comic_favorite(user_id: int, file_id: int):
    """
    Remove comic from user's favorites.

    Args:
        user_id: User ID
        file_id: File ID

    Returns:
        True if successful
    """
    try:
        sb = await get_database()
        await sb.table("comic_favorites").delete().eq("user_id", user_id).eq("file_id", file_id).execute()
        return True
    except Exception:
        return False


async def is_comic_favorite(user_id: int, file_id: int):
    """
    Check if comic is in user's favorites.

    Args:
        user_id: User ID
        file_id: File ID

    Returns:
        True if favorite, False otherwise
    """
    try:
        sb = await get_database()
        result = await sb.table("comic_favorites").select("id").eq("user_id", user_id).eq("file_id", file_id).execute()
        return bool(result.data)
    except Exception:
        return False


async def get_favorite_comics(user_id: int, limit: int = 50, offset: int = 0):
    """
    Get user's favorite comics.

    Args:
        user_id: User ID
        limit: Number of comics to return
        offset: Offset for pagination

    Returns:
        List of favorite comics
    """
    sb = await get_database()

    # Join with comics and files table
    result = await sb.table("comic_favorites").select("*, comics(*, files(*))").eq("user_id", user_id).order("created_at", desc=True).range(offset, offset + limit - 1).execute()

    if result.data:
        return [item.get("comics") for item in result.data if item.get("comics")]
    return []
