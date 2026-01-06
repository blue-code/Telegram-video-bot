"""
User management and quota system for Telegram Video Bot.
"""
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_FREE_QUOTA = 10
DEFAULT_PREMIUM_QUOTA = 999999  # Effectively unlimited


async def get_or_create_user(db_client, telegram_id: int, username: Optional[str] = None) -> dict:
    """
    Get user from database or create new user if doesn't exist.
    
    Args:
        db_client: Supabase async client
        telegram_id: Telegram user ID
        username: Telegram username (optional)
        
    Returns:
        User data dictionary
    """
    try:
        # Try to get existing user
        result = await db_client.table("users").select("*").eq("telegram_id", telegram_id).execute()
        
        if result.data:
            user = result.data[0]
            
            # Check if quota needs to be reset (daily reset)
            last_reset = datetime.fromisoformat(user['last_reset'].replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            
            if now - last_reset >= timedelta(days=1):
                # Reset daily quota
                user = await reset_daily_quota(db_client, telegram_id)
            
            return user
        
        # Create new user
        new_user = {
            "telegram_id": telegram_id,
            "username": username,
            "tier": "free",
            "daily_quota": DEFAULT_FREE_QUOTA,
            "downloads_today": 0,
            "total_downloads": 0
        }
        
        result = await db_client.table("users").insert(new_user).execute()
        logger.info(f"Created new user: {telegram_id}")
        
        return result.data[0]
        
    except Exception as e:
        logger.error(f"Error in get_or_create_user: {e}")
        # Return a default user object if DB fails
        return {
            "telegram_id": telegram_id,
            "username": username,
            "tier": "free",
            "daily_quota": DEFAULT_FREE_QUOTA,
            "downloads_today": 0,
            "total_downloads": 0
        }


async def reset_daily_quota(db_client, telegram_id: int) -> dict:
    """
    Reset the daily download quota for a user.
    
    Args:
        db_client: Supabase async client
        telegram_id: Telegram user ID
        
    Returns:
        Updated user data
    """
    try:
        result = await db_client.table("users").update({
            "downloads_today": 0,
            "last_reset": datetime.now(timezone.utc).isoformat()
        }).eq("telegram_id", telegram_id).execute()
        
        if result.data:
            logger.info(f"Reset daily quota for user {telegram_id}")
            return result.data[0]
        
        return None
        
    except Exception as e:
        logger.error(f"Error resetting quota for {telegram_id}: {e}")
        return None


async def check_quota(db_client, telegram_id: int, username: Optional[str] = None) -> tuple[bool, dict]:
    """
    Check if user has remaining quota for downloads.
    
    Args:
        db_client: Supabase async client
        telegram_id: Telegram user ID
        username: Telegram username (optional)
        
    Returns:
        Tuple of (has_quota: bool, user_data: dict)
    """
    user = await get_or_create_user(db_client, telegram_id, username)
    
    if user['tier'] == 'premium':
        return True, user
    
    has_quota = user['downloads_today'] < user['daily_quota']
    return has_quota, user


async def increment_download_count(db_client, telegram_id: int) -> bool:
    """
    Increment the download count for a user.
    
    Args:
        db_client: Supabase async client
        telegram_id: Telegram user ID
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Get current user
        result = await db_client.table("users").select("downloads_today, total_downloads").eq("telegram_id", telegram_id).execute()
        
        if not result.data:
            logger.error(f"User {telegram_id} not found when incrementing download count")
            return False
        
        user = result.data[0]
        
        # Update counts
        await db_client.table("users").update({
            "downloads_today": user['downloads_today'] + 1,
            "total_downloads": user['total_downloads'] + 1
        }).eq("telegram_id", telegram_id).execute()
        
        logger.info(f"Incremented download count for user {telegram_id}")
        return True
        
    except Exception as e:
        logger.error(f"Error incrementing download count: {e}")
        return False


async def set_user_tier(db_client, telegram_id: int, tier: str) -> bool:
    """
    Set the tier for a user (free or premium).
    
    Args:
        db_client: Supabase async client
        telegram_id: Telegram user ID
        tier: 'free' or 'premium'
        
    Returns:
        True if successful, False otherwise
    """
    try:
        quota = DEFAULT_PREMIUM_QUOTA if tier == 'premium' else DEFAULT_FREE_QUOTA
        
        result = await db_client.table("users").update({
            "tier": tier,
            "daily_quota": quota
        }).eq("telegram_id", telegram_id).execute()
        
        if result.data:
            logger.info(f"Updated user {telegram_id} to {tier} tier")
            return True
        
        return False
        
    except Exception as e:
        logger.error(f"Error setting user tier: {e}")
        return False


async def get_user_stats(db_client, telegram_id: int) -> Optional[dict]:
    """
    Get statistics for a user.
    
    Args:
        db_client: Supabase async client
        telegram_id: Telegram user ID
        
    Returns:
        Dictionary with user statistics or None if not found
    """
    try:
        user_result = await db_client.table("users").select("*").eq("telegram_id", telegram_id).execute()
        
        if not user_result.data:
            return None
        
        user = user_result.data[0]
        
        # Get video count (exclude split parts)
        videos_result = await db_client.table("videos").select("id, metadata").eq("user_id", telegram_id).execute()
        video_count = 0
        for video in videos_result.data or []:
            metadata = video.get("metadata") or {}
            part_index = metadata.get("part_index")
            if part_index is None:
                video_count += 1
                continue
            try:
                if int(part_index) <= 1:
                    video_count += 1
            except (TypeError, ValueError):
                video_count += 1
        
        # Get total storage (sum of file sizes)
        storage_result = await db_client.table("videos").select("file_size").eq("user_id", telegram_id).execute()
        total_storage = sum(v.get('file_size', 0) for v in storage_result.data) if storage_result.data else 0
        
        # Get favorites count
        favs_result = await db_client.table("favorites").select("id", count="exact").eq("user_id", telegram_id).execute()
        favorites_count = favs_result.count if hasattr(favs_result, 'count') else 0
        
        return {
            "user": user,
            "video_count": video_count,
            "total_storage": total_storage,
            "favorites_count": favorites_count
        }
        
    except Exception as e:
        logger.error(f"Error getting user stats: {e}")
        return None
