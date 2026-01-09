from fastapi import FastAPI, HTTPException, Request, Header, Body, File, UploadFile, Form
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import asyncio
import mimetypes
import os
import httpx
import logging
import json
import subprocess
import tempfile
import shutil
from urllib.parse import quote
from datetime import datetime
from dotenv import load_dotenv
from typing import Optional, Tuple
from pathlib import Path
import hashlib
import time
import re
import traceback

# Initialize
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="TVB API", version="1.0.0")
DEFAULT_USER_ID = 41509535
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "41509535"))
MAX_WEB_UPLOAD_SIZE = 15 * 1024 * 1024  # 15MB to stay under Telegram getFile limit.

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

templates = Jinja2Templates(directory="templates")

# Create static directory if not exists and mount it
Path("static").mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# File info cache for metadata (file_path, file_size, etc.)
# Format: {file_id: {"url": str, "size": int, "timestamp": float}}
file_info_cache = {}
CACHE_TTL = 3600  # 1 hour cache TTL
MAX_CACHE_SIZE = 1000  # Maximum number of cached entries

# Progress tracking for downloads
# Format: {task_id: {"status": str, "progress": float, "title": str, "error": str}}
download_progress = {}

# Adaptive chunk size constants
CHUNK_SIZE_SMALL = 32768    # 32KB - for slow networks, initial buffering
CHUNK_SIZE_MEDIUM = 65536   # 64KB - default balanced size
CHUNK_SIZE_LARGE = 131072   # 128KB - for fast networks
CHUNK_SIZE_XLARGE = 262144  # 256KB - for very fast networks


# Utility Functions
def clean_cache_if_needed():
    """Remove oldest cache entries if cache size exceeds limit"""
    if len(file_info_cache) > MAX_CACHE_SIZE:
        # Sort by timestamp and keep only the most recent MAX_CACHE_SIZE entries
        sorted_items = sorted(
            file_info_cache.items(),
            key=lambda x: x[1].get("timestamp", 0),
            reverse=True
        )
        file_info_cache.clear()
        file_info_cache.update(dict(sorted_items[:MAX_CACHE_SIZE]))
        logger.info(f"Cache cleaned: {len(file_info_cache)} entries remaining")


def get_adaptive_chunk_size(connection_speed: Optional[str] = None) -> int:
    """
    Determine optimal chunk size based on connection speed hint.

    Args:
        connection_speed: Client hint for connection quality
                         ("slow-2g", "2g", "3g", "4g", None)

    Returns:
        Optimal chunk size in bytes
    """
    if not connection_speed:
        return CHUNK_SIZE_MEDIUM  # Default balanced size

    speed = connection_speed.lower()
    if speed in ("slow-2g", "2g"):
        return CHUNK_SIZE_SMALL   # 32KB for slow connections
    elif speed == "3g":
        return CHUNK_SIZE_MEDIUM  # 64KB for moderate connections
    elif speed in ("4g", "5g"):
        return CHUNK_SIZE_LARGE   # 128KB for fast connections
    else:
        return CHUNK_SIZE_MEDIUM  # Default


def format_duration(seconds):
    """Format duration in seconds to HH:MM:SS or MM:SS"""
    if not seconds:
        return "00:00"

    try:
        seconds = int(seconds)
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60

        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"
    except (ValueError, TypeError):
        return "00:00"


def format_date(date_str):
    """Format date to relative time (e.g., '2 days ago')"""
    if not date_str:
        return "Unknown"
    
    try:
        # Parse the date string
        if isinstance(date_str, str):
            # Handle ISO format with timezone
            date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        else:
            date = date_str
        
        # Calculate difference
        now = datetime.now(date.tzinfo) if date.tzinfo else datetime.now()
        diff = now - date
        
        # Format relative time
        days = diff.days
        seconds = diff.seconds
        
        if days == 0:
            if seconds < 60:
                return "Just now"
            elif seconds < 3600:
                minutes = seconds // 60
                return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
            else:
                hours = seconds // 3600
                return f"{hours} hour{'s' if hours != 1 else ''} ago"
        elif days == 1:
            return "Yesterday"
        elif days < 7:
            return f"{days} days ago"
        elif days < 30:
            weeks = days // 7
            return f"{weeks} week{'s' if weeks != 1 else ''} ago"
        elif days < 365:
            months = days // 30
            return f"{months} month{'s' if months != 1 else ''} ago"
        else:
            years = days // 365
            return f"{years} year{'s' if years != 1 else ''} ago"
    except Exception as e:
        logger.error(f"Error formatting date: {e}")
        return "Unknown"


def build_thumbnail_url(thumbnail: str) -> str:
    """Normalize thumbnail to a usable URL."""
    if not thumbnail:
        return ""
    if thumbnail.startswith(("http://", "https://", "/")):
        return thumbnail
    return f"/thumb/{quote(thumbnail, safe='')}"


# Mock DB or Bot interaction for now
async def get_file_info_cached(file_id: str) -> Tuple[str, Optional[int]]:
    """
    Get file download URL and size from Telegram, with caching.
    Returns (download_url, file_size_or_none)
    """
    file_id = str(file_id).strip() if file_id is not None else ""
    if not file_id:
        raise HTTPException(status_code=404, detail="File ID is empty")
    
    # Check cache
    now = time.time()
    if file_id in file_info_cache:
        cached = file_info_cache[file_id]
        if now - cached.get("timestamp", 0) < CACHE_TTL:
            logger.debug(f"Cache hit for file_id={file_id}")
            return cached["url"], cached.get("size")
    
    # Cache miss or expired - fetch from Telegram
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="Bot token not valid")
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"https://api.telegram.org/bot{token}/getFile",
            params={"file_id": file_id}
        )
        data = resp.json()
        
        if not data.get("ok"):
            description = data.get("description", "Unknown error")
            logger.error(
                "Telegram getFile failed for file_id=%s: %s",
                file_id,
                description
            )
            if "file is too big" in description.lower():
                raise HTTPException(
                    status_code=413,
                    detail="File too large for Telegram download. Reupload with smaller chunks."
                )
            raise HTTPException(status_code=404, detail="File not found on Telegram")
        
        file_path = data["result"]["file_path"]
        file_size = data["result"].get("file_size")
        download_url = f"https://api.telegram.org/file/bot{token}/{file_path}"
        
        # Update cache
        file_info_cache[file_id] = {
            "url": download_url,
            "size": file_size,
            "timestamp": now
        }
        logger.debug(f"Cache updated for file_id={file_id}")

        # Clean cache if needed
        clean_cache_if_needed()

        return download_url, file_size


async def get_file_path_from_telegram(file_id):
    """
    Legacy function for backward compatibility.
    In a real scenario, we would need to:
    1. Get file_path from getFile API using bot token
    2. Construct download URL: https://api.telegram.org/file/bot<token>/<file_path>
    """
    url, _ = await get_file_info_cached(file_id)
    return url


def parse_range_header(range_header: str, file_size: int) -> Optional[Tuple[int, int]]:
    """
    Parse HTTP Range header.
    Returns (start, end) tuple or None if invalid.
    """
    if not range_header:
        return None
    
    # Parse "bytes=start-end" format
    match = re.match(r'bytes=(\d+)-(\d*)', range_header)
    if not match:
        return None
    
    start = int(match.group(1))
    end_str = match.group(2)
    
    if end_str:
        end = int(end_str)
    else:
        end = file_size - 1
    
    # Validate range
    if start < 0 or start >= file_size:
        return None
    if end >= file_size:
        end = file_size - 1
    if start > end:
        return None
    
    return start, end


def generate_etag(file_id: str) -> str:
    """Generate ETag for a file using SHA-256."""
    return hashlib.sha256(file_id.encode()).hexdigest()[:32]


# Health Check
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "TVB API", "version": "1.0.0"}


# Watch Video - Enhanced
@app.get("/watch/{short_id}", response_class=HTMLResponse)
async def watch_video(request: Request, short_id: str):
    """Enhanced video watch page with metadata"""
    from src.db import get_database, get_video_by_short_id, get_video_by_file_id
    from src.link_shortener import get_or_create_short_link
    
    try:
        if not shutil.which("ffmpeg"):
            raise HTTPException(status_code=500, detail="FFmpeg not available")

        video = await get_video_by_short_id(short_id)
        
        if not video:
            # Fallback: short_id might actually be a file_id
            video = await get_video_by_file_id(short_id)
            if not video:
                return templates.TemplateResponse("error.html", {
                    "request": request,
                    "error_code": 404,
                    "error_message": "Video not found"
                })
            try:
                sb = await get_database()
                resolved_short_id = await get_or_create_short_link(
                    sb,
                    video.get("file_id"),
                    video.get("id"),
                    video.get("user_id") or DEFAULT_USER_ID
                )
                return RedirectResponse(
                    url=f"/watch/{resolved_short_id}",
                    status_code=302
                )
            except Exception as short_error:
                logger.warning(
                    "Failed to resolve short link for file_id=%s: %s",
                    short_id,
                    short_error
                )
        
        metadata = video.get("metadata") or {}
        raw_parts = metadata.get("parts") or []
        playlist = []
        for idx, part in enumerate(raw_parts, start=1):
            if part.get("type") == "audio":
                continue
            file_id = part.get("file_id")
            if not file_id:
                continue
            playlist.append({
                "file_id": file_id,
                "short_id": part.get("short_id"),
                "title": part.get("title", video.get("title", "Unknown")),
                "part": part.get("part", idx)
            })

        if not playlist:
            playlist = [{
                "file_id": video.get("file_id", ""),
                "short_id": short_id,
                "title": video.get("title", "Unknown"),
                "part": 1
            }]

        return templates.TemplateResponse("watch.html", {
            "request": request,
            "short_id": short_id,
            "file_id": video.get('file_id', ''),
            "video_title": video.get('title', 'Unknown'),
            "view_count": video.get('views', 0),
            "duration": format_duration(video.get('duration', 0)),
            "upload_date": format_date(video.get('created_at')),
            "user_id": video.get("user_id") or DEFAULT_USER_ID,
            "playlist": playlist,
            "playlist_total": len(playlist)
        })
    except Exception as e:
        logger.error(f"Error in watch_video: {e}")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_code": 500,
            "error_message": "Internal server error"
        })


@app.get("/stream/{file_id}")
async def stream_video(
    file_id: str,
    range: Optional[str] = Header(None),
    if_none_match: Optional[str] = Header(None),
    request: Request = None
):
    """
    Proxy stream from Telegram to Browser with Range request support.
    Supports HTTP Range requests for video seeking.
    Features adaptive chunk sizing based on network conditions.
    """
    try:
        # Get file info (URL and size) with caching
        download_url, file_size = await get_file_info_cached(file_id)

        # Generate ETag for caching
        etag = generate_etag(file_id)

        # Check If-None-Match for 304 Not Modified
        if if_none_match and if_none_match == etag:
            return Response(status_code=304)

        # Determine optimal chunk size based on client hints
        connection_speed = None
        if request and request.headers:
            # Try to get ECT (Effective Connection Type) from client hints
            connection_speed = request.headers.get("ect") or request.headers.get("downlink")
        chunk_size = get_adaptive_chunk_size(connection_speed)
        logger.debug(f"Using chunk size: {chunk_size} bytes (connection: {connection_speed or 'unknown'})")

        # Parse Range header
        range_tuple = None
        if range and file_size:
            range_tuple = parse_range_header(range, file_size)

        # Prepare headers with Keep-Alive for connection reuse
        headers = {
            "Accept-Ranges": "bytes",
            "ETag": etag,
            "Cache-Control": "public, max-age=3600",
            "Connection": "keep-alive",
            "Keep-Alive": "timeout=60, max=100",  # Keep connection alive for 60s, max 100 requests
        }
        
        # Handle Range request
        if range_tuple and file_size:
            start, end = range_tuple
            content_length = end - start + 1
            
            headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
            headers["Content-Length"] = str(content_length)
            
            logger.info(f"Range request: {start}-{end}/{file_size} for file_id={file_id}")
            
            # Create a generator to stream the requested byte range
            async def iter_range():
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(60.0, read=600.0),
                    follow_redirects=True
                ) as client:
                    # Request the specific range from Telegram
                    range_headers = {"Range": f"bytes={start}-{end}"}
                    async with client.stream("GET", download_url, headers=range_headers) as r:
                        r.raise_for_status()
                        async for chunk in r.aiter_bytes(chunk_size=chunk_size):
                            yield chunk
            
            return StreamingResponse(
                iter_range(),
                status_code=206,
                media_type="video/mp4",
                headers=headers
            )
        
        # Full file request (no Range header)
        if file_size:
            headers["Content-Length"] = str(file_size)

        async def iter_file():
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(60.0, read=600.0),
                follow_redirects=True
            ) as client:
                async with client.stream("GET", download_url) as r:
                    r.raise_for_status()
                    async for chunk in r.aiter_bytes(chunk_size=chunk_size):
                        yield chunk
        
        return StreamingResponse(
            iter_file(),
            media_type="video/mp4",
            headers=headers
        )
        
    except Exception as e:
        logging.error("Streaming error (%s): %r", type(e).__name__, e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/thumb/{file_id}")
async def stream_thumbnail(file_id: str):
    """Proxy stream for thumbnail images stored on Telegram."""
    try:
        download_url = await get_file_path_from_telegram(file_id)
        content_type = mimetypes.guess_type(download_url)[0] or "image/jpeg"

        async def iter_file():
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(60.0, read=300.0),
                follow_redirects=True
            ) as client:
                async with client.stream("GET", download_url) as r:
                    r.raise_for_status()
                    async for chunk in r.aiter_bytes():
                        yield chunk

        return StreamingResponse(iter_file(), media_type=content_type)
    except HTTPException:
        raise
    except Exception as e:
        logging.error("Thumbnail stream error (%s): %r", type(e).__name__, e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stream/concat/{short_id}")
async def stream_concat(short_id: str):
    """
    Proxy stream for multi-part videos by concatenating parts with ffmpeg.
    Improved with better chunk size and buffering.
    """
    from src.db import get_video_by_short_id

    try:
        video = await get_video_by_short_id(short_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")

        metadata = video.get("metadata") or {}
        parts = metadata.get("parts") or []
        if not parts:
            file_id = video.get("file_id")
            if not file_id:
                raise HTTPException(status_code=404, detail="File not available")
            return await stream_video(file_id)

        file_ids = []
        for part in sorted(parts, key=lambda p: p.get("part", 0)):
            raw_id = part.get("file_id")
            if not raw_id:
                continue
            cleaned = str(raw_id).strip()
            if cleaned:
                file_ids.append(cleaned)
        if not file_ids:
            raise HTTPException(status_code=404, detail="No parts available")

        download_urls = await asyncio.gather(
            *[get_file_path_from_telegram(fid) for fid in file_ids]
        )

        async def download_with_retries(client, url, dest_path, label):
            last_error = None
            for attempt in range(1, 4):
                try:
                    async with client.stream("GET", url) as r:
                        r.raise_for_status()
                        with open(dest_path, "wb") as out_file:
                            async for chunk in r.aiter_bytes(chunk_size=131072):  # 128KB chunks
                                out_file.write(chunk)
                    return
                except Exception as err:
                    last_error = err
                    if attempt < 3:
                        logger.warning(
                            "Part download failed (%s attempt %s/3): %s",
                            label,
                            attempt,
                            err
                        )
                        await asyncio.sleep(2 * attempt)
            raise last_error

        temp_dir = tempfile.mkdtemp()
        list_path = os.path.join(temp_dir, "concat.txt")
        local_paths = []
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(60.0, read=600.0),
                follow_redirects=True
            ) as client:
                for idx, url in enumerate(download_urls, start=1):
                    local_path = os.path.join(temp_dir, f"part_{idx}.mp4")
                    await download_with_retries(
                        client,
                        url,
                        local_path,
                        f"part {idx}"
                    )
                    local_paths.append(local_path)

            with open(list_path, "w", encoding="utf-8") as list_file:
                for path in local_paths:
                    list_file.write(f"file '{path}'\n")
        except Exception:
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass
            raise

        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-fflags", "+genpts+igndts",  # Ignore DTS for smoother concat
            "-f", "concat",
            "-safe", "0",
            "-i", list_path,
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            "-max_muxing_queue_size", "9999",  # Prevent queue overflow
            "-movflags", "frag_keyframe+empty_moov+default_base_moof+faststart",  # Added faststart
            "-f", "mp4",
            "pipe:1"
        ]

        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            async def iter_concat():
                try:
                    while True:
                        # Increased chunk size to 1MB for maximum throughput and seamless streaming
                        chunk = await process.stdout.read(1024 * 1024)
                        if not chunk:
                            break
                        yield chunk
                finally:
                    if process.returncode is None:
                        process.terminate()
                        try:
                            await process.wait()
                        except Exception:
                            pass
                    try:
                        shutil.rmtree(temp_dir)
                    except Exception:
                        pass
        except NotImplementedError:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            async def iter_concat():
                try:
                    while True:
                        # Increased chunk size for better throughput
                        chunk = await asyncio.to_thread(
                            process.stdout.read, 1024 * 512
                        )
                        if not chunk:
                            break
                        yield chunk
                finally:
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except Exception:
                            process.kill()
                    try:
                        shutil.rmtree(temp_dir)
                    except Exception:
                        pass

        return StreamingResponse(
            iter_concat(),
            media_type="video/mp4",
            headers={
                "Cache-Control": "public, max-age=3600",
                "Accept-Ranges": "none"  # FFmpeg pipe doesn't support range requests
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logging.error("Concat streaming error (%s): %r", type(e).__name__, e)
        raise HTTPException(status_code=500, detail=str(e))


# Gallery Page
@app.get("/gallery/{user_id}", response_class=HTMLResponse)
async def gallery_page(request: Request, user_id: int):
    """Gallery page showing user's videos"""
    from src.db import get_database, get_user_videos
    from src.link_shortener import get_or_create_short_link
    
    try:
        sb = await get_database()
        videos = await get_user_videos(user_id, limit=100)
        
        formatted_videos = []
        for video in videos:
            short_id = video.get('short_id', '')
            if not short_id:
                file_id = video.get('file_id')
                if file_id:
                    try:
                        short_id = await get_or_create_short_link(
                            sb,
                            file_id,
                            video.get('id'),
                            user_id
                        )
                    except Exception as short_error:
                        logger.warning(
                            "Short link lookup failed for file_id=%s: %s",
                            file_id,
                            short_error
                        )
                        short_id = file_id or ''
            
            formatted_videos.append({
                'id': video.get('id'),
                'short_id': short_id,
                'title': video.get('title', 'Unknown'),
                'thumbnail': build_thumbnail_url(video.get('thumbnail', '')),
                'duration_formatted': format_duration(video.get('duration', 0)),
                'views': video.get('views', 0),
                'date': format_date(video.get('created_at'))
            })
        
        return templates.TemplateResponse("gallery.html", {
            "request": request,
            "user_id": user_id,
            "videos": formatted_videos,
            "videos_json": json.dumps(formatted_videos)
        })
    except Exception as e:
        logger.error(f"Error in gallery_page: {e}")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_code": 500,
            "error_message": "Could not load gallery"
        })


@app.get("/gallery", response_class=HTMLResponse)
async def gallery_default_page(request: Request):
    """Default gallery page using fallback user_id"""
    return await gallery_page(request, DEFAULT_USER_ID)


@app.get("/favorites/{user_id}", response_class=HTMLResponse)
async def favorites_page(request: Request, user_id: int):
    """Favorites page showing user's favorite videos"""
    from src.db import get_user_favorites
    from src.link_shortener import get_or_create_short_link, get_database

    try:
        videos = await get_user_favorites(user_id, limit=100)

        # Add short links for each video
        db = await get_database()
        for video in videos:
            if video.get('file_id'):
                short_id = await get_or_create_short_link(
                    db,
                    video['file_id'],
                    video.get('id'),
                    user_id
                )
                video['short_id'] = short_id

        return templates.TemplateResponse("favorites.html", {
            "request": request,
            "user_id": user_id,
            "videos": videos
        })
    except Exception as e:
        logger.error(f"Error loading favorites: {e}")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error": str(e)
        })


@app.get("/favorites", response_class=HTMLResponse)
async def favorites_default_page(request: Request):
    """Default favorites page using fallback user_id"""
    return await favorites_page(request, DEFAULT_USER_ID)


@app.get("/queue/{user_id}", response_class=HTMLResponse)
async def queue_page(request: Request, user_id: int):
    """Queue management page"""
    return templates.TemplateResponse("queue.html", {
        "request": request,
        "user_id": user_id
    })


@app.get("/queue", response_class=HTMLResponse)
async def queue_default_page(request: Request):
    """Default queue page using fallback user_id"""
    return await queue_page(request, DEFAULT_USER_ID)


@app.get("/api/queue/status")
async def get_queue_status():
    """Get current download queue status"""
    try:
        # Get all active downloads from download_progress
        active_downloads = []

        for task_id, progress_data in download_progress.items():
            if progress_data.get('status') in ['downloading', 'queued']:
                active_downloads.append({
                    'task_id': task_id,
                    'status': progress_data.get('status', 'unknown'),
                    'progress': progress_data.get('progress', 0),
                    'title': progress_data.get('title', 'Unknown'),
                    'error': progress_data.get('error')
                })

        return {
            "success": True,
            "active_downloads": active_downloads,
            "count": len(active_downloads)
        }
    except Exception as e:
        logger.error(f"Error getting queue status: {e}")
        return {
            "success": False,
            "message": str(e)
        }


# REST API Endpoints

# Video increment view
@app.post("/api/increment-view/{short_id}")
async def increment_view(short_id: str, request: Request):
    """Increment view counter for a video (public endpoint)"""
    from src.db import increment_view_count_by_short_id
    
    try:
        # Get client info
        client_host = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent", "")
        
        await increment_view_count_by_short_id(short_id, client_host, user_agent)
        return {"success": True, "message": "View count incremented"}
    except Exception as e:
        logger.error(f"Error incrementing view: {e}")
        return {"success": False, "message": str(e)}


# Resolve short link
@app.get("/api/resolve/{short_id}")
async def resolve_short_link(short_id: str):
    """Resolve short link to video data (public endpoint)"""
    from src.db import get_video_by_short_id
    
    try:
        video = await get_video_by_short_id(short_id)
        
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
        
        return {
            "success": True,
            "data": {
                "file_id": video.get('file_id'),
                "title": video.get('title'),
                "duration": video.get('duration'),
                "views": video.get('views', 0),
                "created_at": video.get('created_at')
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving short link: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Download endpoint
@app.get("/download/{short_id}")
async def download_video(short_id: str):
    """Download video file directly"""
    from src.db import get_video_by_short_id
    
    try:
        video = await get_video_by_short_id(short_id)
        
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")

        metadata = video.get("metadata") or {}
        parts = metadata.get("parts") or []
        if parts:
            title = video.get('title', 'video')
            filename = f"{title}.mp4".replace('/', '_').replace('\\', '_')
            response = await stream_concat(short_id)
            response.headers["Content-Disposition"] = (
                f"attachment; filename=\"{filename}\""
            )
            return response

        file_id = video.get('file_id')
        if not file_id:
            raise HTTPException(status_code=404, detail="File not available")
        
        # Get download URL from Telegram
        download_url = await get_file_path_from_telegram(file_id)
        
        # Stream the file with download headers
        async def iter_file():
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("GET", download_url) as r:
                    async for chunk in r.aiter_bytes():
                        yield chunk
        
        title = video.get('title', 'video')
        filename = f"{title}.mp4".replace('/', '_').replace('\\', '_')
        
        return StreamingResponse(
            iter_file(), 
            media_type="video/mp4",
            headers={"Content-Disposition": f"attachment; filename=\"{filename}\""}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading video: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Protected API endpoints (require X-API-Key header)
from src.api_auth import verify_api_key


@app.get("/api/videos")
async def list_videos(
    user_id: int,
    page: int = 1,
    per_page: int = 20,
    filter: str = "all",
    search: str = "",
    api_key: str = Header(None, alias="X-API-Key")
):
    """List videos with pagination (requires API key)"""
    from src.api_auth import verify_api_key
    
    # Verify API key if configured
    try:
        await verify_api_key(api_key)
    except:
        pass  # Allow if no API key configured
    
    from src.db import get_user_videos
    
    try:
        offset = (page - 1) * per_page
        videos = await get_user_videos(user_id, filter=filter, search=search, limit=per_page, offset=offset)
        
        return {
            "success": True,
            "data": videos,
            "page": page,
            "per_page": per_page,
            "total": len(videos)
        }
    except Exception as e:
        logger.error(f"Error listing videos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/videos/by-url")
async def get_video_by_url_api(
    url: str,
    api_key: str = Header(None, alias="X-API-Key")
):
    """
    Get video by original URL.
    This allows looking up videos downloaded via Telegram bot from the web.
    """
    try:
        await verify_api_key(api_key)
    except:
        pass

    from src.db import get_video_by_url
    from src.link_shortener import get_or_create_short_link

    try:
        video = await get_video_by_url(url)

        if not video:
            return {
                "success": False,
                "found": False,
                "message": "Video not found for this URL"
            }

        # Create streaming link for the video
        sb = await get_database()
        short_id = await get_or_create_short_link(
            sb,
            video.get('file_id'),
            video.get('id'),
            video.get('user_id') or DEFAULT_USER_ID
        )

        return {
            "success": True,
            "found": True,
            "data": video,
            "stream_url": f"/watch/{short_id}"
        }
    except Exception as e:
        logger.error(f"Error getting video by URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/videos/{video_id}")
async def get_video_details(
    video_id: int,
    api_key: str = Header(None, alias="X-API-Key")
):
    """Get video details by ID (requires API key)"""
    try:
        await verify_api_key(api_key)
    except:
        pass

    from src.db import get_video_by_id

    try:
        video = await get_video_by_id(video_id)

        if not video:
            raise HTTPException(status_code=404, detail="Video not found")

        return {
            "success": True,
            "data": video
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting video details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/videos/{video_id}")
async def delete_video(
    video_id: int,
    user_id: int,
    api_key: str = Header(None, alias="X-API-Key")
):
    """Delete video by ID (requires API key)"""
    try:
        await verify_api_key(api_key)
    except:
        pass
    
    from src.db import delete_video_by_id
    
    try:
        success, message = await delete_video_by_id(video_id, user_id)
        
        if success:
            return {"success": True, "message": message}
        else:
            status_code = 404
            if message and "conflict" in message.lower():
                status_code = 409
            raise HTTPException(status_code=status_code, detail=message or "Delete failed")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting video: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/stats/{user_id}")
async def get_user_stats(
    user_id: int,
    api_key: str = Header(None, alias="X-API-Key")
):
    """Get user statistics (requires API key)"""
    try:
        await verify_api_key(api_key)
    except:
        pass
    
    from src.user_manager import get_user_stats
    from src.db import get_database
    
    try:
        stats = await get_user_stats(await get_database(), user_id)
        
        if not stats:
            raise HTTPException(status_code=404, detail="User not found")
        
        return {
            "success": True,
            "data": stats
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/favorites/{user_id}")
async def get_favorites(
    user_id: int,
    api_key: str = Header(None, alias="X-API-Key")
):
    """Get user's favorite videos (requires API key)"""
    try:
        await verify_api_key(api_key)
    except:
        pass
    
    from src.db import get_favorite_videos
    
    try:
        favorites = await get_favorite_videos(user_id)
        
        return {
            "success": True,
            "data": favorites
        }
    except Exception as e:
        logger.error(f"Error getting favorites: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Phase 1: Web Download Page
@app.get("/download", response_class=HTMLResponse)
async def download_page(request: Request, user_id: Optional[int] = None):
    """Web download page"""
    if not user_id:
        user_id = DEFAULT_USER_ID
    return templates.TemplateResponse("download.html", {
        "request": request,
        "user_id": user_id
    })


@app.post("/api/extract-info")
async def extract_video_info_api(url: str = Body(...)):
    """Extract video/playlist information from URL"""
    try:
        from src.downloader import extract_video_info

        info = await extract_video_info(url)

        if info.get('is_playlist'):
            return {
                "success": True,
                "is_playlist": True,
                "playlist_id": info.get('id'),
                "title": info.get('title'),
                "count": info.get('count'),
                "entries": [
                    {
                        "id": entry.get('id'),
                        "title": entry.get('title'),
                        "duration": entry.get('duration'),
                        "url": entry.get('url')
                    }
                    for entry in info.get('entries', [])
                ]
            }
        else:
            return {
                "success": True,
                "is_playlist": False,
                "id": info.get('id'),
                "title": info.get('title'),
                "duration": info.get('duration'),
                "thumbnail": info.get('thumbnail')
            }
    except Exception as e:
        logger.error(f"Error extracting video info: {e}")
        return {
            "success": False,
            "message": str(e)
        }


@app.post("/api/favorites/toggle")
async def toggle_favorite(
    video_id: int = Body(...),
    user_id: int = Body(...)
):
    """Toggle favorite status for a video"""
    try:
        from src.db import is_favorite, add_favorite, remove_favorite

        # Check current status
        is_fav = await is_favorite(user_id, video_id)

        if is_fav:
            # Remove from favorites
            success = await remove_favorite(user_id, video_id)
            return {
                "success": success,
                "is_favorite": False,
                "message": "Removed from favorites"
            }
        else:
            # Add to favorites
            success = await add_favorite(user_id, video_id)
            return {
                "success": success,
                "is_favorite": True,
                "message": "Added to favorites"
            }
    except Exception as e:
        logger.error(f"Error toggling favorite: {e}")
        return {
            "success": False,
            "message": str(e)
        }


@app.get("/stream/progress/{task_id}")
async def stream_progress(task_id: str):
    """
    Server-Sent Events endpoint for real-time download progress.
    """
    async def event_generator():
        try:
            while True:
                # Get progress from global dict
                progress_data = download_progress.get(task_id)

                if not progress_data:
                    yield f"data: {json.dumps({'error': 'Task not found'})}\n\n"
                    await asyncio.sleep(1)
                    continue

                # Send current progress
                data = {
                    "task_id": task_id,
                    "status": progress_data.get("status", "downloading"),
                    "progress": progress_data.get("progress", 0),
                    "title": progress_data.get("title", "Unknown"),
                    "error": progress_data.get("error")
                }

                yield f"data: {json.dumps(data)}\n\n"

                # Stop streaming if task completed or failed
                if progress_data.get("status") in ["completed", "failed", "cancelled"]:
                    break

                # Wait before next update
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            logger.info(f"SSE connection closed for task {task_id}")
        except Exception as e:
            logger.error(f"Error in SSE stream: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/api/web-download")
async def web_download(
    url: str = Body(...),
    quality: str = Body("best"),
    user_id: Optional[int] = Body(None)
):
    """Handle web-based video download - uploads to Telegram"""
    if not user_id:
        user_id = DEFAULT_USER_ID
    downloaded_file = None
    temp_dir = None

    # Generate task ID
    import uuid
    task_id = str(uuid.uuid4())

    # Initialize progress tracking
    download_progress[task_id] = {
        "status": "downloading",
        "progress": 0,
        "title": "Preparing...",
        "error": None
    }

    try:
        logger.info(f"Starting web download: {url} (task_id: {task_id})")

        # Progress hook for yt-dlp
        def progress_hook(d):
            if d['status'] == 'downloading':
                try:
                    total = d.get('total_bytes') or d.get('total_bytes_estimate') or 1
                    downloaded = d.get('downloaded_bytes', 0)
                    progress = (downloaded / total) * 100
                    download_progress[task_id]['progress'] = min(progress, 99)
                    download_progress[task_id]['title'] = d.get('filename', 'Downloading...')
                except Exception as e:
                    logger.error(f"Progress hook error: {e}")

        # Download video using yt-dlp to temporary directory
        import yt_dlp

        temp_dir = tempfile.mkdtemp()
        output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')

        is_audio = str(quality).lower() in {"audio", "bestaudio"}
        if is_audio:
            format_spec = "bestaudio"
        elif str(quality).isdigit():
            format_spec = f"bestvideo[height<={quality}]+bestaudio/best"
        else:
            format_spec = "bestvideo+bestaudio/best"

        ydl_opts = {
            'format': format_spec,
            'outtmpl': output_template,
            'quiet': False,
            'no_warnings': False,
            'progress_hooks': [progress_hook],
            # YouTube 403 Forbidden 우회
            'extractor_args': {
                'youtube': {
                    'player_client': ['android_creator'],
                }
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            },
            'nocheckcertificate': True,
        }
        
        if is_audio:
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
            }]
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'video')
            downloaded_file = ydl.prepare_filename(info)
            
            # Handle audio conversion
            if quality == 'audio':
                downloaded_file = str(Path(downloaded_file).with_suffix('.mp3'))
        
        logger.info(f"Downloaded to: {downloaded_file}")
        
        # Get Telegram credentials
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        bin_channel_id = os.getenv("BIN_CHANNEL_ID")
        
        if not bot_token or not bin_channel_id:
            raise Exception("Telegram credentials not configured")
        
        upload_chat_id = bin_channel_id.strip()
        try:
            upload_chat_id = int(upload_chat_id)
        except ValueError:
            pass

        # Upload to Telegram
        from telegram import Bot
        from telegram.constants import ParseMode
        from telegram.request import HTTPXRequest

        request = HTTPXRequest(
            connect_timeout=60,
            read_timeout=600,
            write_timeout=600,
            pool_timeout=60
        )
        bot = Bot(token=bot_token, request=request)

        async def send_with_retries(send_func, label):
            last_error = None
            for attempt in range(1, 4):
                try:
                    return await send_func()
                except Exception as send_error:
                    last_error = send_error
                    if attempt < 3:
                        logger.warning(
                            "%s attempt %s/3 failed: %s",
                            label,
                            attempt,
                            send_error
                        )
                        await asyncio.sleep(2 * attempt)
            raise last_error

        async def create_thumbnail_file(source_path: str, duration_hint: float) -> str:
            if not shutil.which("ffmpeg"):
                return ""

            if duration_hint and duration_hint > 2:
                thumb_time = min(max(duration_hint * 0.1, 1), duration_hint - 1)
            else:
                thumb_time = 1

            tmp_thumb = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".jpg"
            )
            tmp_thumb.close()

            cmd = [
                "ffmpeg",
                "-y",
                "-ss", str(thumb_time),
                "-i", source_path,
                "-frames:v", "1",
                "-q:v", "2",
                tmp_thumb.name
            ]

            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                returncode = process.returncode
            except NotImplementedError:
                result = await asyncio.to_thread(
                    subprocess.run,
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                stdout = result.stdout
                stderr = result.stderr
                returncode = result.returncode

            if returncode != 0:
                error_msg = stderr.decode(errors="replace")
                logger.warning("Thumbnail generation failed: %s", error_msg)
                try:
                    os.unlink(tmp_thumb.name)
                except OSError:
                    pass
                return ""

            return tmp_thumb.name

        async def upload_thumbnail(path: str) -> str:
            if not path:
                return ""
            with open(path, "rb") as image_file:
                message = await send_with_retries(
                    lambda: bot.send_photo(
                        chat_id=upload_chat_id,
                        photo=image_file,
                        caption="🖼️ Thumbnail"
                    ),
                    "send_photo"
                )
            if message.photo:
                return message.photo[-1].file_id
            return ""

        async def send_document(path, caption):
            with open(path, "rb") as video_file:
                return await bot.send_document(
                    chat_id=upload_chat_id,
                    document=video_file,
                    caption=caption,
                    parse_mode=ParseMode.HTML
                )

        file_size = os.path.getsize(downloaded_file) if downloaded_file else 0
        if not is_audio and file_size > MAX_WEB_UPLOAD_SIZE:
            if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
                raise Exception(
                    "FFmpeg/ffprobe not found. Install FFmpeg and ensure "
                    "ffmpeg/ffprobe are available in PATH."
                )

            logger.info(
                "Downloaded file exceeds limit (%.1fMB). Splitting before upload.",
                file_size / (1024 * 1024)
            )
            from src.splitter import split_video, get_video_duration

            total_duration = info.get("duration") or 0
            if not total_duration:
                try:
                    total_duration = await get_video_duration(downloaded_file)
                except Exception:
                    total_duration = 0

            parts = await split_video(downloaded_file, MAX_WEB_UPLOAD_SIZE, transcode=False)
            total_parts = len(parts)
            parts_metadata = []
            master_file_id = None
            master_thumbnail = ""
            thumbnail_temp_path = ""

            try:
                thumbnail_temp_path = await create_thumbnail_file(
                    downloaded_file,
                    total_duration
                )
                if thumbnail_temp_path:
                    master_thumbnail = await upload_thumbnail(thumbnail_temp_path)
            except Exception as thumb_error:
                logger.warning("Thumbnail upload failed: %s", thumb_error)

            for index, part_path in enumerate(parts, start=1):
                part_title = f"{title} (Part {index}/{total_parts})"
                caption = f"🌐 <b>Web Download</b>\n🎬 {part_title}\n🔗 {url[:100]}..."

                message = await send_with_retries(
                    lambda: send_document(part_path, caption),
                    "send_document"
                )
                if message.document:
                    part_file_id = message.document.file_id
                    part_duration = 0
                elif message.video:
                    part_file_id = message.video.file_id
                    part_duration = message.video.duration or 0
                else:
                    raise Exception("Telegram upload failed")

                if part_duration == 0:
                    try:
                        part_duration = await get_video_duration(part_path)
                    except Exception:
                        part_duration = 0

                if master_file_id is None:
                    master_file_id = part_file_id

                parts_metadata.append({
                    "part": index,
                    "total": total_parts,
                    "title": part_title,
                    "file_id": part_file_id,
                    "duration": part_duration or 0,
                    "type": "video"
                })

            metadata = {
                "parts": parts_metadata,
                "part_index": 1,
                "part_total": total_parts,
                "is_master": True
            }

            from src.db import get_database
            from src.link_shortener import create_short_link
            sb = await get_database()

            video_data = {
                "file_id": master_file_id,
                "title": title,
                "duration": total_duration,
                "thumbnail": master_thumbnail,
                "user_id": user_id,
                "url": url,
                "metadata": metadata
            }

            video_id = None
            try:
                result = await sb.table("videos").insert(video_data).execute()
                if result.data:
                    video_id = result.data[0].get("id")
            except Exception as db_error:
                logger.error("Video metadata insert failed: %s", db_error)

            if video_id is None and master_file_id:
                try:
                    lookup = await sb.table("videos").select("id").eq(
                        "file_id", master_file_id
                    ).eq("user_id", user_id).order(
                        "created_at",
                        desc=True
                    ).limit(1).execute()
                    if lookup.data:
                        video_id = lookup.data[0].get("id")
                except Exception as lookup_error:
                    logger.warning(
                        "Video lookup after insert failed: %s",
                        lookup_error
                    )

            short_id = await create_short_link(
                sb,
                master_file_id,
                video_id,
                user_id
            )

            logger.info("Upload successful! file_id: %s", master_file_id)

            # Update progress to completed
            download_progress[task_id]['status'] = 'completed'
            download_progress[task_id]['progress'] = 100
            download_progress[task_id]['title'] = title

            if downloaded_file and os.path.exists(downloaded_file):
                os.unlink(downloaded_file)
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
            for path in parts:
                if path != downloaded_file and os.path.exists(path):
                    try:
                        os.unlink(path)
                    except OSError:
                        pass
            if thumbnail_temp_path and os.path.exists(thumbnail_temp_path):
                try:
                    os.unlink(thumbnail_temp_path)
                except OSError:
                    pass

            return {
                "success": True,
                "task_id": task_id,
                "short_id": short_id,
                "title": title,
                "message": "✅ Download and upload complete!"
            }

        logger.info(f"Uploading {title} to Telegram...")

        with open(downloaded_file, 'rb') as video_file:
            if is_audio:
                message = await bot.send_audio(
                    chat_id=upload_chat_id,
                    audio=video_file,
                    caption=f"🌐 <b>Web Download</b>\n🎵 {title}\n🔗 {url[:100]}...",
                    parse_mode=ParseMode.HTML,
                    read_timeout=300,
                    write_timeout=300
                )
                file_id = message.audio.file_id
                duration = message.audio.duration or 0
                thumbnail = message.audio.thumbnail.file_id if message.audio.thumbnail else ""
            else:
                message = await bot.send_video(
                    chat_id=upload_chat_id,
                    video=video_file,
                    caption=f"🌐 <b>Web Download</b>\n🎬 {title}\n🔗 {url[:100]}...",
                    parse_mode=ParseMode.HTML,
                    supports_streaming=True,
                    read_timeout=300,
                    write_timeout=300
                )
                file_id = message.video.file_id
                duration = message.video.duration or 0
                thumbnail = message.video.thumbnail.file_id if message.video.thumbnail else ""
        
        logger.info(f"Upload successful! file_id: {file_id}")
        
        # Delete downloaded file and temp directory
        if downloaded_file and os.path.exists(downloaded_file):
            os.unlink(downloaded_file)
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
        logger.info("Cleaned up temporary files")
        
        # Generate short link
        from src.link_shortener import generate_short_id
        short_id = generate_short_id()
        
        # Save metadata to database
        from src.db import get_database
        sb = await get_database()
        
        video_data = {
            "file_id": file_id,
            "title": title,
            "duration": duration,
            "thumbnail": thumbnail,
            "user_id": user_id,
            "url": url  # Save original URL
        }
        
        result = await sb.table("videos").insert(video_data).execute()
        
        if result.data:
            video_id = result.data[0]['id']
            
            # Create short link
            await sb.table("shared_links").insert({
                "short_id": short_id,
                "file_id": file_id,
                "video_id": video_id,
                "user_id": user_id,
                "views": 0
            }).execute()
        
        logger.info(f"Video metadata saved: video_id={video_id}, short_id={short_id}")

        # Update progress to completed
        download_progress[task_id]['status'] = 'completed'
        download_progress[task_id]['progress'] = 100
        download_progress[task_id]['title'] = title

        return {
            "success": True,
            "task_id": task_id,
            "short_id": short_id,
            "title": title,
            "message": "✅ Download and upload complete!"
        }
        
    except Exception as e:
        logger.error(f"Web download error: {e}")

        # Update progress to failed
        download_progress[task_id]['status'] = 'failed'
        download_progress[task_id]['error'] = str(e)

        # Cleanup on error
        if downloaded_file and os.path.exists(downloaded_file):
            try:
                os.unlink(downloaded_file)
            except:
                pass
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
            except:
                pass

        return {
            "success": False,
            "task_id": task_id,
            "message": f"Download failed: {str(e)}"
        }


# Phase 1: Dashboard Page
@app.get("/dashboard/{user_id}", response_class=HTMLResponse)
async def dashboard_page(request: Request, user_id: int):
    """User dashboard with statistics and quick access"""
    from src.user_manager import get_user_stats
    from src.db import get_database, get_user_videos
    from src.link_shortener import get_or_create_short_link
    
    try:
        # Get user stats
        sb = await get_database()
        stats = await get_user_stats(sb, user_id)
        
        # Get recent videos
        recent_videos = await get_user_videos(user_id, limit=5)
        
        # Format videos
        formatted_videos = []
        for video in recent_videos:
            short_id = video.get('short_id', '')
            if not short_id:
                file_id = video.get('file_id')
                if file_id:
                    try:
                        short_id = await get_or_create_short_link(
                            sb,
                            file_id,
                            video.get('id'),
                            user_id
                        )
                    except Exception as short_error:
                        logger.warning(
                            "Short link lookup failed for file_id=%s: %s",
                            file_id,
                            short_error
                        )
                        short_id = file_id or ''

            formatted_videos.append({
                'id': video.get('id'),
                'short_id': short_id,
                'title': video.get('title', 'Unknown'),
                'thumbnail': build_thumbnail_url(video.get('thumbnail', '')),
                'duration': format_duration(video.get('duration', 0)),
                'views': video.get('views', 0),
                'date': format_date(video.get('created_at'))
            })
        
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "user_id": user_id,
            "stats": stats,
            "recent_videos": formatted_videos
        })
    except Exception as e:
        logger.error(f"Dashboard error: {e}")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_code": 500,
            "error_message": "Could not load dashboard"
        })


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_default_page(request: Request):
    """Default dashboard page using fallback user_id"""
    return await dashboard_page(request, DEFAULT_USER_ID)


# Phase 1: Advanced Search Page
@app.get("/search", response_class=HTMLResponse)
async def search_page(
    request: Request,
    user_id: Optional[int] = None,
    q: str = "",
    date_from: str = "",
    date_to: str = "",
    duration: str = "all",
    sort: str = "latest"
):
    """Advanced search page with filters"""
    from src.db import get_database, search_videos, get_video_by_url
    from src.link_shortener import get_or_create_short_link

    try:
        if not user_id:
            user_id = DEFAULT_USER_ID
        sb = await get_database()

        # Check if query looks like a URL - redirect to watch page if found
        if q and (q.startswith('http://') or q.startswith('https://')):
            video = await get_video_by_url(q)
            if video:
                short_id = await get_or_create_short_link(
                    sb,
                    video.get('file_id'),
                    video.get('id'),
                    video.get('user_id') or DEFAULT_USER_ID
                )
                return RedirectResponse(url=f"/watch/{short_id}", status_code=302)

        # Search videos with filters
        results = await search_videos(
            user_id=user_id,
            query=q,
            date_from=date_from,
            date_to=date_to,
            duration_filter=duration,
            sort_by=sort,
            limit=100
        )
        
        formatted_results = []
        for video in results:
            short_id = video.get('short_id', '')
            if not short_id:
                file_id = video.get('file_id')
                if file_id:
                    try:
                        short_id = await get_or_create_short_link(
                            sb,
                            file_id,
                            video.get('id'),
                            user_id
                        )
                    except Exception as short_error:
                        logger.warning(
                            "Short link lookup failed for file_id=%s: %s",
                            file_id,
                            short_error
                        )
                        short_id = file_id or ''
            formatted_results.append({
                'id': video.get('id'),
                'short_id': short_id,
                'title': video.get('title', 'Unknown'),
                'thumbnail': build_thumbnail_url(video.get('thumbnail', '')),
                'duration_formatted': format_duration(video.get('duration', 0)),
                'views': video.get('views', 0),
                'date': format_date(video.get('created_at'))
            })
        
        return templates.TemplateResponse("search.html", {
            "request": request,
            "user_id": user_id,
            "query": q,
            "results": formatted_results,
            "total": len(formatted_results)
        })
    except Exception as e:
        logger.error(f"Search error: {e}")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_code": 500,
            "error_message": "Search failed"
        })


# Phase 3: File Upload Feature
@app.post("/api/upload-file")
async def upload_file(
    file: UploadFile = File(...),
    user_id: Optional[int] = Form(None)
):
    """Upload local video file to Telegram (not local storage)"""
    tmp_path = None

    try:
        if not user_id:
            user_id = DEFAULT_USER_ID

        # Save to temporary file
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=Path(file.filename).suffix
        ) as tmp_file:
            shutil.copyfileobj(file.file, tmp_file)
            tmp_path = tmp_file.name

        logger.info("Temporary file saved: %s", tmp_path)

        total_duration = 0
        try:
            from src.splitter import get_video_duration
            total_duration = await get_video_duration(tmp_path)
        except Exception as duration_error:
            logger.warning(
                "Duration probe failed for %s: %s",
                tmp_path,
                duration_error
            )

        file_size = os.path.getsize(tmp_path)
        if file_size > MAX_WEB_UPLOAD_SIZE:
            if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
                raise Exception(
                    "FFmpeg/ffprobe not found. Install FFmpeg and ensure "
                    "ffmpeg/ffprobe are available in PATH."
                )
            logger.info(
                "File exceeds limit (%.1fMB), splitting into parts.",
                file_size / (1024 * 1024)
            )
            from src.splitter import split_video
            parts = await split_video(
                tmp_path,
                MAX_WEB_UPLOAD_SIZE,
                transcode=False
            )
        else:
            parts = [tmp_path]

        # Get Telegram credentials
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        bin_channel_id = os.getenv("BIN_CHANNEL_ID")

        if not bot_token:
            raise Exception("TELEGRAM_BOT_TOKEN not configured in .env")

        upload_chat_id = user_id
        if bin_channel_id:
            bin_channel_id = bin_channel_id.strip()
            try:
                upload_chat_id = int(bin_channel_id)
            except ValueError:
                upload_chat_id = bin_channel_id
        else:
            logger.info("BIN_CHANNEL_ID not set; uploading to user_id=%s", user_id)

        # Upload to Telegram
        from telegram import Bot
        from telegram.constants import ParseMode
        from telegram.request import HTTPXRequest

        request = HTTPXRequest(
            connect_timeout=60,
            read_timeout=600,
            write_timeout=600,
            pool_timeout=60
        )
        bot = Bot(token=bot_token, request=request)

        async def send_with_retries(send_func, label):
            last_error = None
            for attempt in range(1, 4):
                try:
                    return await send_func()
                except Exception as send_error:
                    last_error = send_error
                    if attempt < 3:
                        logger.warning(
                            "%s attempt %s/3 failed: %s",
                            label,
                            attempt,
                            send_error
                        )
                        await asyncio.sleep(2 * attempt)
            raise last_error

        async def create_thumbnail_file(source_path: str, duration_hint: float) -> str:
            if not shutil.which("ffmpeg"):
                return ""

            if duration_hint and duration_hint > 2:
                thumb_time = min(max(duration_hint * 0.1, 1), duration_hint - 1)
            else:
                thumb_time = 1

            tmp_thumb = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=".jpg"
            )
            tmp_thumb.close()

            cmd = [
                "ffmpeg",
                "-y",
                "-ss", str(thumb_time),
                "-i", source_path,
                "-frames:v", "1",
                "-q:v", "2",
                tmp_thumb.name
            ]

            try:
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()
                returncode = process.returncode
            except NotImplementedError:
                result = await asyncio.to_thread(
                    subprocess.run,
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                stdout = result.stdout
                stderr = result.stderr
                returncode = result.returncode

            if returncode != 0:
                error_msg = stderr.decode(errors="replace")
                logger.warning("Thumbnail generation failed: %s", error_msg)
                try:
                    os.unlink(tmp_thumb.name)
                except OSError:
                    pass
                return ""

            return tmp_thumb.name

        async def upload_thumbnail(path: str) -> str:
            if not path:
                return ""
            with open(path, "rb") as image_file:
                message = await send_with_retries(
                    lambda: bot.send_photo(
                        chat_id=upload_chat_id,
                        photo=image_file,
                        caption="🖼️ Thumbnail"
                    ),
                    "send_photo"
                )
            if message.photo:
                return message.photo[-1].file_id
            return ""

        async def send_document(path, caption):
            with open(path, "rb") as video_file:
                return await bot.send_document(
                    chat_id=upload_chat_id,
                    document=video_file,
                    caption=caption,
                    parse_mode=ParseMode.HTML
                )

        async def upload_part(path, part_label):
            caption = (
                f"📤 <b>Web Upload</b>\n📁 {part_label}\n👤 User: {user_id}"
            )
            message = await send_with_retries(
                lambda: send_document(path, caption),
                "send_document"
            )
            if message.document:
                return (message.document.file_id, 0, "")
            if message.video:
                return (message.video.file_id, message.video.duration or 0, "")
            logger.error(
                "send_document returned no document/video for %s: %s",
                part_label,
                message.to_dict() if hasattr(message, "to_dict") else message
            )
            raise Exception("Telegram upload failed")

        # Save metadata to database (single master record)
        from src.db import get_database
        from src.link_shortener import create_short_link
        sb = await get_database()

        total_parts = len(parts)
        parts_metadata = []
        master_file_id = None
        master_thumbnail = ""
        thumbnail_temp_path = ""

        try:
            thumbnail_temp_path = await create_thumbnail_file(
                tmp_path,
                total_duration
            )
            if thumbnail_temp_path:
                master_thumbnail = await upload_thumbnail(thumbnail_temp_path)
        except Exception as thumb_error:
            logger.warning("Thumbnail upload failed: %s", thumb_error)

        for index, part_path in enumerate(parts, start=1):
            if total_parts == 1:
                part_title = file.filename
            else:
                part_title = (
                    f"{Path(file.filename).stem} (Part {index}/{total_parts})"
                    f"{Path(file.filename).suffix}"
                )

            try:
                part_size = os.path.getsize(part_path)
                logger.info(
                    "Uploading %s to Telegram chat_id=%s (%.1fMB)...",
                    part_title,
                    upload_chat_id,
                    part_size / (1024 * 1024)
                )
            except OSError:
                logger.info(
                    "Uploading %s to Telegram chat_id=%s...",
                    part_title,
                    upload_chat_id
                )

            file_id, duration, thumbnail = await upload_part(
                part_path,
                part_title
            )

            if master_file_id is None:
                master_file_id = file_id
                if not master_thumbnail and thumbnail:
                    master_thumbnail = thumbnail

            total_duration += duration or 0
            parts_metadata.append({
                "part": index,
                "total": total_parts,
                "title": part_title,
                "file_id": file_id,
                "duration": duration or 0,
                "type": "video"
            })

        metadata = None
        if total_parts > 1:
            metadata = {
                "parts": parts_metadata,
                "part_index": 1,
                "part_total": total_parts,
                "is_master": True
            }

        video_data = {
            "file_id": master_file_id,
            "title": file.filename,
            "duration": total_duration,
            "thumbnail": master_thumbnail,
            "user_id": user_id,
            "url": None
        }
        if metadata:
            video_data["metadata"] = metadata

        video_id = None
        try:
            result = await sb.table("videos").insert(video_data).execute()
            if result.data:
                video_id = result.data[0].get("id")
            else:
                logger.warning("Video insert returned no data: %s", result)
        except Exception as db_error:
            logger.error("Video metadata insert failed: %s", db_error)

        if video_id is None and master_file_id:
            try:
                lookup = await sb.table("videos").select("id").eq(
                    "file_id", master_file_id
                ).eq("user_id", user_id).order(
                    "created_at",
                    desc=True
                ).limit(1).execute()
                if lookup.data:
                    video_id = lookup.data[0].get("id")
            except Exception as lookup_error:
                logger.warning(
                    "Video lookup after insert failed: %s",
                    lookup_error
                )

        short_id = await create_short_link(
            sb,
            master_file_id,
            video_id,
            user_id
        )

        logger.info("Upload successful! parts=%s", total_parts)

        # Delete temporary file(s) immediately
        cleanup_paths = set(parts + [tmp_path])
        if thumbnail_temp_path:
            cleanup_paths.add(thumbnail_temp_path)
        for path in cleanup_paths:
            if path and os.path.exists(path):
                os.unlink(path)
                logger.info("Temporary file deleted: %s", path)

        message = "✅ Uploaded to Telegram successfully!"

        return {
            "success": True,
            "short_id": short_id,
            "filename": file.filename,
            "file_id": master_file_id,
            "message": message
        }

    except Exception as e:
        logger.error("File upload error (%s): %r", type(e).__name__, e)

        # Cleanup temporary file on error
        paths_to_cleanup = set()
        if tmp_path:
            paths_to_cleanup.add(tmp_path)
        if locals().get("thumbnail_temp_path"):
            paths_to_cleanup.add(locals().get("thumbnail_temp_path"))
        for path in locals().get("parts", []):
            if path:
                paths_to_cleanup.add(path)

        for path in paths_to_cleanup:
            if os.path.exists(path):
                try:
                    os.unlink(path)
                    logger.info("Cleaned up temporary file after error: %s", path)
                except Exception as cleanup_error:
                    logger.error("Failed to cleanup temp file: %s", cleanup_error)

        message = str(e) or "Upload failed due to an unexpected error."
        return {
            "success": False,
            "message": message
        }


# Phase 3: Video Editing Features
@app.get("/edit/{video_id}", response_class=HTMLResponse)
async def edit_page(request: Request, video_id: int, user_id: Optional[int] = None):
    """Video editing page"""
    from src.db import get_video_by_id
    
    try:
        if not user_id:
            user_id = DEFAULT_USER_ID
        video = await get_video_by_id(video_id)
        
        if not video or (video.get('user_id') != user_id and user_id != SUPER_ADMIN_ID):
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error_code": 403,
                "error_message": "Access denied"
            })

        video["thumbnail"] = build_thumbnail_url(video.get("thumbnail", ""))
        
        return templates.TemplateResponse("edit.html", {
            "request": request,
            "video": video,
            "user_id": user_id
        })
    except Exception as e:
        logger.error(f"Edit page error: {e}")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_code": 500,
            "error_message": "Could not load edit page"
        })


@app.put("/api/videos/{video_id}")
async def update_video(
    video_id: int,
    title: str = Body(None),
    description: str = Body(None),
    tags: list = Body([]),
    user_id: int = Body(...)
):
    """Update video metadata"""
    from src.db import update_video_metadata
    
    try:
        success = await update_video_metadata(
            video_id=video_id,
            user_id=user_id,
            title=title,
            description=description,
            tags=tags
        )
        
        return {"success": success}
    except Exception as e:
        logger.error(f"Update video error: {e}")
        return {"success": False, "message": str(e)}


# HLS (HTTP Live Streaming) Endpoints
HLS_CACHE_DIR = Path("hls_cache")
HLS_CACHE_DIR.mkdir(exist_ok=True)
HLS_SEGMENT_DURATION = 2  # seconds per segment (shorter = faster start, smoother playback)
INITIAL_PART_COUNT = 5  # 첫 번째로 처리할 파트 개수 (빠른 재생 시작용)

# Lock dictionary to prevent concurrent HLS generation for the same video
hls_generation_locks = {}

# Background task tracking
background_tasks = {}


async def extend_hls_in_background(short_id: str, initial_parts: list, all_parts: list, hls_dir: Path, video: dict):
    """
    백그라운드에서 나머지 파트를 처리하여 HLS를 확장합니다.

    Args:
        short_id: 비디오 short ID
        initial_parts: 이미 처리된 초기 파트 리스트
        all_parts: 전체 파트 리스트
        hls_dir: HLS 디렉토리 경로
        video: 비디오 정보 dict
    """
    try:
        logger.info(f"🔄 Background HLS extension started for {short_id}")

        # 나머지 파트 추출
        remaining_parts = all_parts[len(initial_parts):]
        if not remaining_parts:
            logger.info(f"   No remaining parts to process for {short_id}")
            return

        logger.info(f"   Processing {len(remaining_parts)} remaining parts")

        # 나머지 파트의 file_ids 추출
        file_ids = [p.get("file_id") for p in sorted(remaining_parts, key=lambda x: x.get("part", 0))]
        download_urls = await asyncio.gather(
            *[get_file_path_from_telegram(fid) for fid in file_ids if fid]
        )

        # 임시 디렉토리에 다운로드
        temp_dir = tempfile.mkdtemp()
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, read=600.0)) as client:
                part_files = []
                for idx, url in enumerate(download_urls, len(initial_parts) + 1):
                    part_path = os.path.join(temp_dir, f"part_{idx}.mp4")
                    async with client.stream("GET", url) as r:
                        r.raise_for_status()
                        with open(part_path, "wb") as f:
                            async for chunk in r.aiter_bytes(chunk_size=CHUNK_SIZE_LARGE):
                                f.write(chunk)
                    part_files.append(part_path)

                logger.info(f"   Downloaded {len(part_files)} additional parts")

                # 추가 파트 concat
                concat_list = os.path.join(temp_dir, "remaining.txt")
                with open(concat_list, "w") as f:
                    for pf in part_files:
                        f.write(f"file '{pf}'\n")

                remaining_video = os.path.join(temp_dir, "remaining.mp4")
                concat_cmd = [
                    "ffmpeg", "-f", "concat", "-safe", "0",
                    "-i", concat_list, "-c", "copy", remaining_video
                ]
                subprocess.run(concat_cmd, check=True, capture_output=True)

                # 기존 세그먼트 개수 확인
                existing_segments = sorted(hls_dir.glob("segment*.m4s"))
                start_number = len(existing_segments)

                logger.info(f"   Starting segment generation from #{start_number}")

                # 추가 HLS 세그먼트 생성
                output_pattern = str(hls_dir / f"segment%03d.m4s")
                temp_playlist = str(hls_dir / "temp.m3u8")

                hls_cmd = [
                    "ffmpeg",
                    "-i", remaining_video,
                    "-c:v", "copy",
                    "-c:a", "copy",
                    "-f", "hls",
                    "-hls_time", str(HLS_SEGMENT_DURATION),
                    "-hls_list_size", "0",
                    "-hls_segment_type", "fmp4",
                    "-hls_flags", "independent_segments",
                    "-start_number", str(start_number),
                    "-hls_playlist_type", "vod",
                    "-hls_segment_filename", output_pattern,
                    "-movflags", "+faststart",
                    temp_playlist
                ]

                result = subprocess.run(hls_cmd, capture_output=True, text=True, timeout=300)

                if result.returncode != 0:
                    logger.error(f"❌ Background HLS extension failed: {result.stderr[:500]}")
                    return

                # temp playlist에서 새 세그먼트 정보 추출하여 기존 playlist에 추가
                with open(temp_playlist, "r") as f:
                    temp_content = f.read()

                # index.m3u8 업데이트
                index_playlist = hls_dir / "index.m3u8"
                with open(index_playlist, "r") as f:
                    original_content = f.read()

                # EVENT 타입을 VOD로 변경하고 새 세그먼트 추가
                updated_content = original_content.replace("#EXT-X-PLAYLIST-TYPE:EVENT", "#EXT-X-PLAYLIST-TYPE:VOD")

                # 기존 #EXT-X-ENDLIST 제거 (있다면)
                updated_content = updated_content.replace("#EXT-X-ENDLIST\n", "")

                # 새 세그먼트 추가 (temp playlist에서 추출)
                temp_lines = temp_content.split("\n")
                for i, line in enumerate(temp_lines):
                    if line.startswith("#EXTINF:") or line.startswith("segment"):
                        updated_content += line + "\n"

                # #EXT-X-ENDLIST 추가
                if not updated_content.endswith("#EXT-X-ENDLIST\n"):
                    updated_content += "#EXT-X-ENDLIST\n"

                with open(index_playlist, "w") as f:
                    f.write(updated_content)

                # temp playlist 삭제
                os.remove(temp_playlist)

                new_segment_count = len(list(hls_dir.glob("segment*.m4s")))
                logger.info(f"✅ Background HLS extension completed for {short_id}")
                logger.info(f"   Total segments: {new_segment_count}")

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    except Exception as e:
        logger.error(f"❌ Background HLS extension failed for {short_id}")
        logger.error(f"   Exception: {type(e).__name__}: {str(e)}")
        logger.error(f"   Traceback:\n{traceback.format_exc()}")
    finally:
        # 백그라운드 태스크 추적에서 제거
        if short_id in background_tasks:
            del background_tasks[short_id]


async def generate_hls_for_video(short_id: str) -> Optional[Path]:
    """
    Generate HLS segments and playlist for a video.
    Returns the directory containing HLS files or None if failed.
    Uses async lock to prevent concurrent generation of the same video.
    """
    from src.db import get_video_by_short_id

    logger.info(f"🎬 HLS generation requested for {short_id}")

    # Get or create lock for this video
    if short_id not in hls_generation_locks:
        hls_generation_locks[short_id] = asyncio.Lock()

    lock = hls_generation_locks[short_id]

    # Try to acquire lock (wait if another generation is in progress)
    if lock.locked():
        logger.info(f"⏳ HLS generation already in progress for {short_id}, waiting...")

    async with lock:
        try:
            # Check cache first (after acquiring lock)
            hls_dir = HLS_CACHE_DIR / short_id
            master_playlist = hls_dir / "master.m3u8"

            if master_playlist.exists():
                logger.info(f"✅ HLS cache hit for {short_id}")
                # Verify segments exist
                segments = list(hls_dir.glob("segment*.m4s"))
                logger.info(f"   Found {len(segments)} cached segments")
                return hls_dir

            logger.info(f"🔨 No cache found, generating HLS for {short_id}")

            # Get video info
            video = await get_video_by_short_id(short_id)
            if not video:
                logger.error(f"❌ Video not found in database: {short_id}")
                return None

            logger.info(f"📹 Video found: {video.get('title', 'Unknown')}")

            # Create HLS directory
            hls_dir.mkdir(parents=True, exist_ok=True)

            # Get video file
            metadata = video.get("metadata") or {}
            parts = metadata.get("parts") or []

            logger.info(f"   Metadata parts: {len(parts)} parts detected")

            # Initialize variables for partial processing
            is_partial = False
            sorted_parts = None
            parts_to_process = None

            # For multi-part videos, concatenate first
            if parts and len(parts) > 1:
                logger.info(f"   Processing multi-part video ({len(parts)} parts)")

                # Sort all parts
                sorted_parts = sorted(parts, key=lambda x: x.get("part", 0))

                # ★ 부분 처리 로직: 처음 5개 파트만 우선 처리
                is_partial = len(sorted_parts) > INITIAL_PART_COUNT
                parts_to_process = sorted_parts[:INITIAL_PART_COUNT] if is_partial else sorted_parts

                if is_partial:
                    logger.info(f"   ⚡ Quick start mode: Processing first {len(parts_to_process)} parts (total {len(sorted_parts)})")
                else:
                    logger.info(f"   Processing all {len(parts_to_process)} parts")

                # Download and concatenate initial parts
                file_ids = [p.get("file_id") for p in parts_to_process]
                download_urls = await asyncio.gather(
                    *[get_file_path_from_telegram(fid) for fid in file_ids if fid]
                )

                # Download parts to temp directory
                temp_dir = tempfile.mkdtemp()
                try:
                    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, read=600.0)) as client:
                        part_files = []
                        for idx, url in enumerate(download_urls, 1):
                            part_path = os.path.join(temp_dir, f"part_{idx}.mp4")
                            async with client.stream("GET", url) as r:
                                r.raise_for_status()
                                with open(part_path, "wb") as f:
                                    async for chunk in r.aiter_bytes(chunk_size=CHUNK_SIZE_LARGE):
                                        f.write(chunk)
                            part_files.append(part_path)

                        # Concatenate using ffmpeg
                        concat_list = os.path.join(temp_dir, "concat.txt")
                        with open(concat_list, "w") as f:
                            for pf in part_files:
                                f.write(f"file '{pf}'\n")

                        input_video = os.path.join(temp_dir, "full.mp4")
                        concat_cmd = [
                            "ffmpeg", "-f", "concat", "-safe", "0",
                            "-i", concat_list, "-c", "copy", input_video
                        ]
                        subprocess.run(concat_cmd, check=True, capture_output=True)

                except Exception as e:
                    logger.error(f"Part concatenation failed: {e}")
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    return None
            else:
                # Single file - download it
                logger.info(f"   Processing single video file")
                file_id = video.get("file_id")
                if not file_id:
                    logger.error(f"❌ No file_id for video {short_id}")
                    return None

                logger.info(f"   Getting download URL for file_id: {file_id[:20]}...")
                download_url = await get_file_path_from_telegram(file_id)
                logger.info(f"   Download URL obtained, starting download...")
                temp_dir = tempfile.mkdtemp()

                try:
                    input_video = os.path.join(temp_dir, "video.mp4")
                    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, read=600.0)) as client:
                        async with client.stream("GET", download_url) as r:
                            r.raise_for_status()
                            with open(input_video, "wb") as f:
                                async for chunk in r.aiter_bytes(chunk_size=CHUNK_SIZE_LARGE):
                                    f.write(chunk)
                    logger.info(f"   Video download completed: {os.path.getsize(input_video)} bytes")
                except Exception as e:
                    logger.error(f"❌ Video download failed: {type(e).__name__}: {e}")
                    logger.error(f"   Traceback:\n{traceback.format_exc()}")
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    return None

            # Generate HLS segments
            try:
                # fMP4 파일 경로 (전체 경로 지정)
                output_pattern = str(hls_dir / "segment%03d.m4s")
                playlist_path = str(hls_dir / "index.m3u8")
                init_segment_path = str(hls_dir / "init.mp4")  # ★ 전체 경로로 지정!

                # ★ 부분 처리 시 EVENT, 전체 처리 시 VOD
                playlist_type = "event" if is_partial else "vod"
                logger.info(f"   Using playlist type: {playlist_type} (partial={is_partial})")

                hls_cmd = [
                    "ffmpeg",
                    "-i", input_video,
                    "-c:v", "copy",              # 비디오 코덱 복사 (재인코딩 없음)
                    "-c:a", "copy",              # 오디오 코덱 복사 (재인코딩 없음)
                    "-f", "hls",
                    "-hls_time", str(HLS_SEGMENT_DURATION),
                    "-hls_list_size", "0",
                    "-hls_segment_type", "fmp4",  # ★ fMP4 사용 (MPEG-TS 대신)
                    "-hls_fmp4_init_filename", init_segment_path,  # ★ 전체 경로로 지정!
                    "-hls_flags", "independent_segments",
                    "-start_number", "0",
                    "-hls_playlist_type", playlist_type,  # ★ 조건부 playlist type
                    "-hls_segment_filename", output_pattern,
                    "-movflags", "+faststart",   # MP4 최적화
                    playlist_path
                ]

                logger.info(f"⚙️ Starting HLS generation for {short_id}")
                logger.info(f"   Output dir: {hls_dir}")
                logger.info(f"   Temp dir: {temp_dir}")
                logger.info(f"   Full command: {' '.join(hls_cmd)}")
                result = subprocess.run(hls_cmd, capture_output=True, text=True, timeout=300)

                if result.returncode != 0:
                    logger.error(f"❌ ffmpeg failed (return code {result.returncode})")
                    logger.error(f"   stderr: {result.stderr[:500]}")  # First 500 chars
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    return None

                logger.info(f"✅ ffmpeg completed successfully")
                if result.stderr:
                    logger.info(f"   ffmpeg stderr (first 500 chars): {result.stderr[:500]}")

                # Verify segments were created (fMP4 uses .m4s extension)
                segments = list(hls_dir.glob("segment*.m4s"))
                init_segment = hls_dir / "init.mp4"
                all_files = list(hls_dir.glob("*"))

                logger.info(f"   Checking for segments in {hls_dir}")
                logger.info(f"   Directory exists: {hls_dir.exists()}")
                logger.info(f"   Total files in directory: {len(all_files)}")
                logger.info(f"   First 5 files: {[f.name for f in all_files[:5]]}")
                logger.info(f"   init.mp4 exists: {init_segment.exists()}")
                logger.info(f"   Found {len(segments)} .m4s segments")

                if not segments:
                    logger.error(f"❌ No HLS segments generated for {short_id}")
                    logger.error(f"   Directory contents: {[f.name for f in hls_dir.glob('*')]}")
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    return None

                logger.info(f"✅ Generated {len(segments)} HLS segments for {short_id}")

                # ★ 플레이리스트의 전체 경로를 상대 경로로 수정
                index_playlist = hls_dir / "index.m3u8"
                if index_playlist.exists():
                    with open(index_playlist, "r") as f:
                        playlist_content = f.read()

                    # Windows/Unix 경로 구분자 모두 처리
                    hls_dir_str = str(hls_dir).replace("\\", "/")
                    playlist_content = playlist_content.replace(f"{hls_dir_str}/", "")
                    playlist_content = playlist_content.replace(str(hls_dir) + "\\", "")

                    with open(index_playlist, "w") as f:
                        f.write(playlist_content)

                    logger.info(f"✅ Playlist paths normalized to relative paths")

                # Create master playlist
                with open(master_playlist, "w") as f:
                    f.write("#EXTM3U\n")
                    f.write("#EXT-X-VERSION:3\n")
                    f.write("#EXT-X-STREAM-INF:BANDWIDTH=5000000\n")
                    f.write("index.m3u8\n")

                logger.info(f"HLS generated successfully for {short_id}")
                shutil.rmtree(temp_dir, ignore_errors=True)

                # ★ 부분 처리인 경우 백그라운드에서 나머지 확장
                if is_partial and sorted_parts and parts_to_process:
                    logger.info(f"🔄 Launching background task to extend HLS with remaining parts")
                    task = asyncio.create_task(
                        extend_hls_in_background(
                            short_id=short_id,
                            initial_parts=parts_to_process,
                            all_parts=sorted_parts,
                            hls_dir=hls_dir,
                            video=video
                        )
                    )
                    background_tasks[short_id] = task
                    logger.info(f"✅ Background task launched for {short_id}")

                return hls_dir

            except subprocess.TimeoutExpired:
                logger.error(f"HLS generation timeout for {short_id}")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return None
            except Exception as e:
                logger.error(f"HLS generation error: {e}")
                shutil.rmtree(temp_dir, ignore_errors=True)
                return None

        except Exception as e:
            logger.error(f"❌ HLS generation failed for {short_id}")
            logger.error(f"   Exception: {type(e).__name__}: {str(e)}")
            logger.error(f"   Traceback:\n{traceback.format_exc()}")
            return None


@app.api_route("/api/hls/{short_id}/{filename}", methods=["GET", "HEAD"])
async def serve_hls_file(request: Request, short_id: str, filename: str):
    """Serve HLS playlist or segment files"""
    try:
        # Generate HLS if not exists
        hls_dir = await generate_hls_for_video(short_id)

        if not hls_dir:
            raise HTTPException(status_code=404, detail="HLS generation failed")

        file_path = hls_dir / filename

        if not file_path.exists():
            raise HTTPException(status_code=404, detail="File not found")

        # Determine media type
        if filename.endswith(".m3u8"):
            media_type = "application/vnd.apple.mpegurl"
        elif filename.endswith(".m4s") or filename.endswith(".mp4"):
            media_type = "video/mp4"  # fMP4 segments
        elif filename.endswith(".ts"):
            media_type = "video/MP2T"  # Legacy MPEG-TS (fallback)
        else:
            media_type = "application/octet-stream"

        # HEAD 요청은 헤더만 반환
        if request.method == "HEAD":
            return Response(
                headers={
                    "Content-Type": media_type,
                    "Content-Length": str(file_path.stat().st_size),
                    "Cache-Control": "public, max-age=3600",
                    "Access-Control-Allow-Origin": "*",
                    "Connection": "keep-alive",
                    "Keep-Alive": "timeout=60, max=100"
                }
            )

        return FileResponse(
            file_path,
            media_type=media_type,
            headers={
                "Cache-Control": "public, max-age=3600",
                "Access-Control-Allow-Origin": "*",
                "Connection": "keep-alive",
                "Keep-Alive": "timeout=60, max=100"
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"HLS file serve error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
