"""
Database functions for bookmarks, series, and read completion tracking.
"""
from typing import List, Dict, Optional
from datetime import datetime
import json


# ============================================================
# Read Completion Tracking
# ============================================================

async def mark_content_completed(user_id: int, file_id: str, content_type: str, is_completed: bool):
    """
    Mark EPUB or Comic as completed/uncompleted.

    Args:
        user_id: User ID
        file_id: File ID (Telegram file_id)
        content_type: 'epub' or 'comic'
        is_completed: True to mark as completed, False to unmark
    """
    from src.db import get_database

    sb = await get_database()

    table = "files" if content_type == "epub" else "comics"

    update_data = {
        "is_completed": is_completed,
        "completed_at": datetime.now().isoformat() if is_completed else None
    }

    result = await sb.table(table).update(update_data).eq("file_id", file_id).eq("user_id", user_id).execute()

    return result.data[0] if result.data else None


async def get_completion_status(user_id: int, file_id: str, content_type: str) -> bool:
    """
    Get completion status for a book or comic.

    Returns:
        True if completed, False otherwise
    """
    from src.db import get_database

    sb = await get_database()
    table = "files" if content_type == "epub" else "comics"

    result = await sb.table(table).select("is_completed").eq("file_id", file_id).eq("user_id", user_id).execute()

    if result.data:
        return result.data[0].get("is_completed", False)
    return False


async def get_completed_count(user_id: int, content_type: str) -> int:
    """
    Get count of completed books/comics.
    """
    from src.db import get_database

    sb = await get_database()
    table = "files" if content_type == "epub" else "comics"

    result = await sb.table(table).select("id", count="exact").eq("user_id", user_id).eq("is_completed", True).execute()

    return result.count if result.count else 0


# ============================================================
# Bookmarks
# ============================================================

async def create_bookmark(
    user_id: int,
    file_id: str,
    content_type: str,
    bookmark_position: dict,
    title: str,
    note: Optional[str] = None,
    thumbnail: Optional[str] = None
) -> Dict:
    """
    Create a bookmark.

    Args:
        user_id: User ID
        file_id: File ID
        content_type: 'epub' or 'comic'
        bookmark_position: {"cfi": "...", "percentage": 0.5, "page": 10}
        title: Bookmark title
        note: Optional note
        thumbnail: Optional thumbnail (base64 or file_id)

    Returns:
        Created bookmark dict
    """
    from src.db import get_database

    sb = await get_database()

    bookmark = {
        "user_id": user_id,
        "file_id": file_id,
        "content_type": content_type,
        "bookmark_position": json.dumps(bookmark_position),
        "title": title,
        "note": note,
        "thumbnail": thumbnail
    }

    result = await sb.table("bookmarks").insert(bookmark).execute()

    return result.data[0] if result.data else None


async def get_bookmarks(
    user_id: int,
    file_id: Optional[str] = None,
    content_type: Optional[str] = None
) -> List[Dict]:
    """
    Get bookmarks for user, optionally filtered by file or content type.

    Args:
        user_id: User ID
        file_id: Optional file ID filter
        content_type: Optional content type filter ('epub' or 'comic')

    Returns:
        List of bookmarks
    """
    from src.db import get_database

    sb = await get_database()

    q = sb.table("bookmarks").select("*").eq("user_id", user_id)

    if file_id:
        q = q.eq("file_id", file_id)

    if content_type:
        q = q.eq("content_type", content_type)

    q = q.order("created_at", desc=True)

    result = await q.execute()

    bookmarks = result.data if result.data else []

    # Parse bookmark_position JSON
    for bookmark in bookmarks:
        if "bookmark_position" in bookmark and isinstance(bookmark["bookmark_position"], str):
            bookmark["bookmark_position"] = json.loads(bookmark["bookmark_position"])

    return bookmarks


async def delete_bookmark(bookmark_id: int, user_id: int) -> bool:
    """
    Delete a bookmark (user must own it).

    Returns:
        True if deleted, False otherwise
    """
    from src.db import get_database

    sb = await get_database()

    result = await sb.table("bookmarks").delete().eq("id", bookmark_id).eq("user_id", user_id).execute()

    return len(result.data) > 0 if result.data else False


async def update_bookmark(
    bookmark_id: int,
    user_id: int,
    title: Optional[str] = None,
    note: Optional[str] = None
) -> Dict:
    """
    Update bookmark title or note.

    Returns:
        Updated bookmark dict
    """
    from src.db import get_database

    sb = await get_database()

    update_data = {}
    if title is not None:
        update_data["title"] = title
    if note is not None:
        update_data["note"] = note

    if not update_data:
        return None

    result = await sb.table("bookmarks").update(update_data).eq("id", bookmark_id).eq("user_id", user_id).execute()

    return result.data[0] if result.data else None


# ============================================================
# Series Management
# ============================================================

async def create_series(
    user_id: int,
    title: str,
    description: Optional[str] = None,
    content_type: str = "mixed",
    cover_image: Optional[str] = None,
    metadata: Optional[dict] = None
) -> Dict:
    """
    Create a new series.

    Args:
        user_id: User ID
        title: Series title
        description: Optional description
        content_type: 'epub', 'comic', or 'mixed'
        cover_image: Optional cover image (base64 or file_id)
        metadata: Optional metadata dict

    Returns:
        Created series dict
    """
    from src.db import get_database

    sb = await get_database()

    series = {
        "user_id": user_id,
        "title": title,
        "description": description,
        "content_type": content_type,
        "cover_image": cover_image,
        "metadata": json.dumps(metadata) if metadata else "{}"
    }

    result = await sb.table("series").insert(series).execute()

    return result.data[0] if result.data else None


async def get_user_series(
    user_id: int,
    content_type: Optional[str] = None
) -> List[Dict]:
    """
    Get all series for a user, optionally filtered by content type.

    Uses series_with_progress view to include completion stats.

    Returns:
        List of series with progress info
    """
    from src.db import get_database

    sb = await get_database()

    q = sb.table("series_with_progress").select("*").eq("user_id", user_id)

    if content_type:
        q = q.eq("content_type", content_type)

    q = q.order("created_at", desc=True)

    result = await q.execute()

    return result.data if result.data else []


async def get_series_details(series_id: int, user_id: int) -> Optional[Dict]:
    """
    Get series details with progress.

    Returns:
        Series dict with total_items and completed_items
    """
    from src.db import get_database

    sb = await get_database()

    result = await sb.table("series_with_progress").select("*").eq("id", series_id).eq("user_id", user_id).execute()

    return result.data[0] if result.data else None


async def get_series_items(series_id: int, user_id: int) -> List[Dict]:
    """
    Get all items in a series with their details.

    Returns:
        List of items with book/comic details and completion status
    """
    from src.db import get_database

    sb = await get_database()

    # Get series items
    items_result = await sb.table("series_items").select("*").eq("series_id", series_id).order("item_order").execute()

    if not items_result.data:
        return []

    items = []

    for item in items_result.data:
        file_id = item["file_id"]
        content_type = item["content_type"]

        # Fetch book/comic details
        if content_type == "epub":
            detail_result = await sb.table("files").select("*").eq("file_id", file_id).eq("user_id", user_id).execute()
        else:
            detail_result = await sb.table("comics").select("*").eq("file_id", file_id).eq("user_id", user_id).execute()

        if detail_result.data:
            detail = detail_result.data[0]
            items.append({
                "series_item_id": item["id"],
                "file_id": file_id,
                "content_type": content_type,
                "item_order": item["item_order"],
                "title": detail.get("title"),
                "is_completed": detail.get("is_completed", False),
                "metadata": detail.get("metadata", {}),
                **detail  # Include all fields
            })

    return items


async def add_to_series(
    series_id: int,
    file_id: str,
    content_type: str,
    item_order: Optional[int] = None
) -> Dict:
    """
    Add a book/comic to a series.

    Args:
        series_id: Series ID
        file_id: File ID to add
        content_type: 'epub' or 'comic'
        item_order: Optional order (auto-assigns if None)

    Returns:
        Created series_item dict
    """
    from src.db import get_database

    sb = await get_database()

    # If no order specified, get max order + 1
    if item_order is None:
        result = await sb.table("series_items").select("item_order").eq("series_id", series_id).order("item_order", desc=True).limit(1).execute()

        if result.data:
            item_order = result.data[0]["item_order"] + 1
        else:
            item_order = 1

    series_item = {
        "series_id": series_id,
        "file_id": file_id,
        "content_type": content_type,
        "item_order": item_order
    }

    result = await sb.table("series_items").insert(series_item).execute()

    return result.data[0] if result.data else None


async def remove_from_series(series_id: int, file_id: str) -> bool:
    """
    Remove a book/comic from a series.

    Returns:
        True if removed, False otherwise
    """
    from src.db import get_database

    sb = await get_database()

    result = await sb.table("series_items").delete().eq("series_id", series_id).eq("file_id", file_id).execute()

    return len(result.data) > 0 if result.data else False


async def update_series_order(series_id: int, file_id: str, new_order: int) -> Dict:
    """
    Update the order of an item in a series.

    Returns:
        Updated series_item dict
    """
    from src.db import get_database

    sb = await get_database()

    result = await sb.table("series_items").update({"item_order": new_order}).eq("series_id", series_id).eq("file_id", file_id).execute()

    return result.data[0] if result.data else None


async def delete_series(series_id: int, user_id: int) -> bool:
    """
    Delete a series (user must own it).
    Series items will be auto-deleted via CASCADE.

    Returns:
        True if deleted, False otherwise
    """
    from src.db import get_database

    sb = await get_database()

    result = await sb.table("series").delete().eq("id", series_id).eq("user_id", user_id).execute()

    return len(result.data) > 0 if result.data else False


async def update_series(
    series_id: int,
    user_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    cover_image: Optional[str] = None
) -> Dict:
    """
    Update series details.

    Returns:
        Updated series dict
    """
    from src.db import get_database

    sb = await get_database()

    update_data = {}
    if title is not None:
        update_data["title"] = title
    if description is not None:
        update_data["description"] = description
    if cover_image is not None:
        update_data["cover_image"] = cover_image

    if not update_data:
        return None

    result = await sb.table("series").update(update_data).eq("id", series_id).eq("user_id", user_id).execute()

    return result.data[0] if result.data else None


async def get_all_series_file_ids(user_id: int, content_type: Optional[str] = None) -> set:
    """
    Get all file_ids that are in user-created series.

    Args:
        user_id: User ID
        content_type: Optional content type filter ('epub' or 'comic')

    Returns:
        Set of file_ids that are in series
    """
    from src.db import get_database

    sb = await get_database()

    # Get all series for this user
    series_query = sb.table("series").select("id").eq("user_id", user_id)

    if content_type:
        series_query = series_query.eq("content_type", content_type)

    series_result = await series_query.execute()

    if not series_result.data:
        return set()

    series_ids = [s["id"] for s in series_result.data]

    # Get all file_ids in these series
    items_query = sb.table("series_items").select("file_id").in_("series_id", series_ids)

    if content_type:
        items_query = items_query.eq("content_type", content_type)

    items_result = await items_query.execute()

    if not items_result.data:
        return set()

    file_ids = {item["file_id"] for item in items_result.data}

    return file_ids
