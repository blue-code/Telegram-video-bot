"""
FastAPI routes for bookmarks, series, and read completion tracking.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
import logging

from src.db_bookmarks_series import (
    mark_content_completed,
    get_completion_status,
    get_completed_count,
    create_bookmark,
    get_bookmarks,
    delete_bookmark,
    update_bookmark,
    create_series,
    get_user_series,
    get_series_details,
    get_series_items,
    add_to_series,
    remove_from_series,
    update_series_order,
    delete_series,
    update_series
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================
# Pydantic Models
# ============================================================

class CompletionRequest(BaseModel):
    file_id: str
    content_type: str  # 'epub' or 'comic'
    is_completed: bool


class BookmarkCreate(BaseModel):
    file_id: str
    content_type: str
    bookmark_position: dict  # {"cfi": "...", "percentage": 0.5, "page": 10}
    title: str
    note: Optional[str] = None
    thumbnail: Optional[str] = None


class BookmarkUpdate(BaseModel):
    title: Optional[str] = None
    note: Optional[str] = None


class SeriesCreate(BaseModel):
    title: str
    description: Optional[str] = None
    content_type: str = "mixed"  # 'epub', 'comic', or 'mixed'
    cover_image: Optional[str] = None


class SeriesUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    cover_image: Optional[str] = None


class SeriesItemAdd(BaseModel):
    file_id: str
    content_type: str  # 'epub' or 'comic'
    item_order: Optional[int] = None


class SeriesItemOrderUpdate(BaseModel):
    file_id: str
    new_order: int


# ============================================================
# Read Completion Routes
# ============================================================

@router.post("/api/completion/mark")
async def api_mark_completed(request: CompletionRequest, user_id: int):
    """
    Mark a book or comic as completed/uncompleted.
    """
    try:
        result = await mark_content_completed(
            user_id=user_id,
            file_id=request.file_id,
            content_type=request.content_type,
            is_completed=request.is_completed
        )

        if not result:
            raise HTTPException(status_code=404, detail="Content not found")

        return {"success": True, "data": result}

    except Exception as e:
        logger.error(f"Error marking completion: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/completion/status/{content_type}/{file_id}")
async def api_get_completion_status(content_type: str, file_id: str, user_id: int):
    """
    Get completion status for a book or comic.
    """
    try:
        is_completed = await get_completion_status(user_id, file_id, content_type)
        return {"file_id": file_id, "content_type": content_type, "is_completed": is_completed}

    except Exception as e:
        logger.error(f"Error getting completion status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/completion/count/{content_type}")
async def api_get_completed_count(content_type: str, user_id: int):
    """
    Get count of completed books/comics.
    """
    try:
        count = await get_completed_count(user_id, content_type)
        return {"content_type": content_type, "completed_count": count}

    except Exception as e:
        logger.error(f"Error getting completed count: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Bookmark Routes
# ============================================================

@router.post("/api/bookmarks")
async def api_create_bookmark(request: BookmarkCreate, user_id: int):
    """
    Create a new bookmark.
    """
    try:
        bookmark = await create_bookmark(
            user_id=user_id,
            file_id=request.file_id,
            content_type=request.content_type,
            bookmark_position=request.bookmark_position,
            title=request.title,
            note=request.note,
            thumbnail=request.thumbnail
        )

        if not bookmark:
            raise HTTPException(status_code=500, detail="Failed to create bookmark")

        return {"success": True, "data": bookmark}

    except Exception as e:
        logger.error(f"Error creating bookmark: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/bookmarks")
async def api_get_bookmarks(
    user_id: int,
    file_id: Optional[str] = None,
    content_type: Optional[str] = None
):
    """
    Get bookmarks for user, optionally filtered.
    """
    try:
        bookmarks = await get_bookmarks(user_id, file_id, content_type)
        return {"success": True, "data": bookmarks, "count": len(bookmarks)}

    except Exception as e:
        logger.error(f"Error getting bookmarks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/bookmarks/{bookmark_id}")
async def api_delete_bookmark(bookmark_id: int, user_id: int):
    """
    Delete a bookmark.
    """
    try:
        success = await delete_bookmark(bookmark_id, user_id)

        if not success:
            raise HTTPException(status_code=404, detail="Bookmark not found or not owned by user")

        return {"success": True, "message": "Bookmark deleted"}

    except Exception as e:
        logger.error(f"Error deleting bookmark: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/bookmarks/{bookmark_id}")
async def api_update_bookmark(bookmark_id: int, request: BookmarkUpdate, user_id: int):
    """
    Update bookmark title or note.
    """
    try:
        bookmark = await update_bookmark(
            bookmark_id=bookmark_id,
            user_id=user_id,
            title=request.title,
            note=request.note
        )

        if not bookmark:
            raise HTTPException(status_code=404, detail="Bookmark not found or not owned by user")

        return {"success": True, "data": bookmark}

    except Exception as e:
        logger.error(f"Error updating bookmark: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# Series Routes
# ============================================================

@router.post("/api/series")
async def api_create_series(request: SeriesCreate, user_id: int):
    """
    Create a new series.
    """
    try:
        series = await create_series(
            user_id=user_id,
            title=request.title,
            description=request.description,
            content_type=request.content_type,
            cover_image=request.cover_image
        )

        if not series:
            raise HTTPException(status_code=500, detail="Failed to create series")

        return {"success": True, "data": series}

    except Exception as e:
        logger.error(f"Error creating series: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/series")
async def api_get_user_series(user_id: int, content_type: Optional[str] = None):
    """
    Get all series for user.
    """
    try:
        series_list = await get_user_series(user_id, content_type)
        return {"success": True, "data": series_list, "count": len(series_list)}

    except Exception as e:
        logger.error(f"Error getting series: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/series/{series_id}")
async def api_get_series_details(series_id: int, user_id: int):
    """
    Get series details with progress.
    """
    try:
        series = await get_series_details(series_id, user_id)

        if not series:
            raise HTTPException(status_code=404, detail="Series not found")

        return {"success": True, "data": series}

    except Exception as e:
        logger.error(f"Error getting series details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/api/series/{series_id}/items")
async def api_get_series_items(series_id: int, user_id: int):
    """
    Get all items in a series.
    """
    try:
        items = await get_series_items(series_id, user_id)
        return {"success": True, "data": items, "count": len(items)}

    except Exception as e:
        logger.error(f"Error getting series items: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/series/{series_id}/items")
async def api_add_to_series(series_id: int, request: SeriesItemAdd, user_id: int):
    """
    Add a book/comic to a series.
    Validates that content_type matches the series type.
    """
    try:
        # Verify user owns the series
        series = await get_series_details(series_id, user_id)
        if not series:
            raise HTTPException(status_code=404, detail="Series not found")

        # Validation: Check content_type compatibility
        series_type = series.get('content_type', 'mixed')

        if series_type != 'mixed' and series_type != request.content_type:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot add {request.content_type} to {series_type} series. Content types must match."
            )

        # If series is 'mixed', block it for now (can be enabled later)
        if series_type == 'mixed':
            raise HTTPException(
                status_code=400,
                detail="Mixed-type series are not currently supported. Please use separate series for EPUB and comics."
            )

        item = await add_to_series(
            series_id=series_id,
            file_id=request.file_id,
            content_type=request.content_type,
            item_order=request.item_order
        )

        if not item:
            raise HTTPException(status_code=500, detail="Failed to add to series")

        return {"success": True, "data": item}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding to series: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/series/{series_id}/items/{file_id}")
async def api_remove_from_series(series_id: int, file_id: str, user_id: int):
    """
    Remove a book/comic from a series.
    """
    try:
        # Verify user owns the series
        series = await get_series_details(series_id, user_id)
        if not series:
            raise HTTPException(status_code=404, detail="Series not found")

        success = await remove_from_series(series_id, file_id)

        if not success:
            raise HTTPException(status_code=404, detail="Item not found in series")

        return {"success": True, "message": "Item removed from series"}

    except Exception as e:
        logger.error(f"Error removing from series: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/series/{series_id}/items/order")
async def api_update_series_order(series_id: int, request: SeriesItemOrderUpdate, user_id: int):
    """
    Update the order of an item in a series.
    """
    try:
        # Verify user owns the series
        series = await get_series_details(series_id, user_id)
        if not series:
            raise HTTPException(status_code=404, detail="Series not found")

        item = await update_series_order(series_id, request.file_id, request.new_order)

        if not item:
            raise HTTPException(status_code=404, detail="Item not found in series")

        return {"success": True, "data": item}

    except Exception as e:
        logger.error(f"Error updating series order: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/api/series/{series_id}")
async def api_delete_series(series_id: int, user_id: int):
    """
    Delete a series.
    """
    try:
        success = await delete_series(series_id, user_id)

        if not success:
            raise HTTPException(status_code=404, detail="Series not found or not owned by user")

        return {"success": True, "message": "Series deleted"}

    except Exception as e:
        logger.error(f"Error deleting series: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/api/series/{series_id}")
async def api_update_series(series_id: int, request: SeriesUpdate, user_id: int):
    """
    Update series details.
    """
    try:
        series = await update_series(
            series_id=series_id,
            user_id=user_id,
            title=request.title,
            description=request.description,
            cover_image=request.cover_image
        )

        if not series:
            raise HTTPException(status_code=404, detail="Series not found or not owned by user")

        return {"success": True, "data": series}

    except Exception as e:
        logger.error(f"Error updating series: {e}")
        raise HTTPException(status_code=500, detail=str(e))
