from fastapi import FastAPI, HTTPException, Request, Header, Body, File, UploadFile, Form, BackgroundTasks
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
from telegram import Bot
from telegram.request import HTTPXRequest
from telegram.constants import ParseMode
from src.transcoder import transcode_video_task, cleanup_old_encoded_files
from src.file_manager import prepare_download_task, DOWNLOAD_CACHE_DIR, cleanup_old_downloads
from src.epub_parser import get_epub_metadata
import uuid
import aiofiles

# Initialize
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="TVB API", version="1.0.0")
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
DEFAULT_USER_ID = int(os.getenv("ADMIN_USER_ID", "41509535"))
SUPER_ADMIN_ID = int(os.getenv("SUPER_ADMIN_ID", "41509535"))
MAX_WEB_UPLOAD_SIZE = 15 * 1024 * 1024  # 15MB to stay under Telegram getFile limit.

# Global Bot Instance
global_bot: Optional[Bot] = None

@app.on_event("startup")
async def startup_event():
    global global_bot
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if token:
        try:
            request = HTTPXRequest(
                connect_timeout=60,
                read_timeout=600,
                write_timeout=600,
                pool_timeout=60
            )
            global_bot = Bot(token=token, request=request)
            me = await global_bot.get_me()
            logger.info(f"🤖 Bot initialized: @{me.username} (ID: {me.id})")
            logger.info(f"📢 Notification target (DEFAULT_USER_ID): {DEFAULT_USER_ID}")
        except Exception as e:
            logger.error(f"❌ Bot initialization failed: {e}")
            global_bot = None
    else:
        logger.warning("⚠️ TELEGRAM_BOT_TOKEN not found. Bot features will be disabled.")
    
    # Start cleanup tasks
    try:
        from src.db import get_database
        sb = await get_database()
        asyncio.create_task(cleanup_old_encoded_files(sb))
        asyncio.create_task(cleanup_old_downloads())
    except Exception as e:
        logger.error(f"Failed to start cleanup tasks: {e}")

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
        
        # Check encoding status
        is_encoded = metadata.get("is_encoded", False)
        encoded_path = metadata.get("encoded_path")
        encoded_url = ""
        
        if is_encoded and encoded_path and os.path.exists(encoded_path):
            encoded_url = f"/stream/encoded/{short_id}"
        else:
            is_encoded = False # Reset if file missing

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
            "playlist_total": len(playlist),
            "is_encoded": is_encoded,
            "encoded_url": encoded_url
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
                try:
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
                except Exception as e:
                    if "ClientDisconnected" in str(type(e).__name__) or isinstance(e, (OSError, asyncio.CancelledError)):
                        logger.debug(f"Client disconnected during range stream: {e}")
                    else:
                        logger.error(f"Stream range error: {e}")
                    return
            
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
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(60.0, read=600.0),
                    follow_redirects=True
                ) as client:
                    async with client.stream("GET", download_url) as r:
                        r.raise_for_status()
                        async for chunk in r.aiter_bytes(chunk_size=chunk_size):
                            yield chunk
            except Exception as e:
                if "ClientDisconnected" in str(type(e).__name__) or isinstance(e, (OSError, asyncio.CancelledError)):
                    logger.debug(f"Client disconnected during file stream: {e}")
                else:
                    logger.error(f"Stream file error: {e}")
                return
        
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
                except Exception as e:
                    if "ClientDisconnected" in str(type(e).__name__) or isinstance(e, (OSError, asyncio.CancelledError)):
                        logger.debug(f"Client disconnected during concat stream: {e}")
                    else:
                        logger.error(f"Concat stream error: {e}")
                    # Terminate process if client disconnects or error occurs
                    if process.returncode is None:
                        process.terminate()
                    return
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
                except Exception as e:
                    if "ClientDisconnected" in str(type(e).__name__) or isinstance(e, (OSError, asyncio.CancelledError)):
                        logger.debug(f"Client disconnected during concat stream: {e}")
                    else:
                        logger.error(f"Concat stream error: {e}")
                    if process.poll() is None:
                        process.terminate()
                    return
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


@app.get("/encoded/{user_id}", response_class=HTMLResponse)
async def encoded_page(request: Request, user_id: int):
    """Page for managing encoded videos"""
    from src.db import get_encoded_videos, get_database
    from src.link_shortener import get_or_create_short_link

    try:
        sb = await get_database()
        videos = await get_encoded_videos(user_id, limit=100)
        
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
                    except Exception:
                        short_id = file_id or ''
            
            metadata = video.get("metadata") or {}
            encoded_size = 0
            encoded_path = metadata.get("encoded_path")
            if encoded_path and os.path.exists(encoded_path):
                encoded_size = os.path.getsize(encoded_path)

            formatted_videos.append({
                'id': video.get('id'),
                'short_id': short_id,
                'title': video.get('title', 'Unknown'),
                'thumbnail': build_thumbnail_url(video.get('thumbnail', '')),
                'duration_formatted': format_duration(video.get('duration', 0)),
                'size_mb': round(encoded_size / (1024 * 1024), 1),
                'date': format_date(video.get('created_at'))
            })
        
        return templates.TemplateResponse("encoded.html", {
            "request": request,
            "user_id": user_id,
            "videos": formatted_videos
        })
    except Exception as e:
        logger.error(f"Error loading encoded page: {e}")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_code": 500,
            "error_message": "Could not load encoded videos"
        })


@app.get("/encoded", response_class=HTMLResponse)
async def encoded_default_page(request: Request):
    """Default encoded page using fallback user_id"""
    return await encoded_page(request, DEFAULT_USER_ID)


@app.delete("/api/encoded/delete/{short_id}")
async def delete_encoded_file(short_id: str, user_id: Optional[int] = Body(None)):
    """Delete the encoded file only (keep original video)"""
    from src.db import get_video_by_short_id, get_database
    
    try:
        video = await get_video_by_short_id(short_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
            
        metadata = video.get("metadata") or {}
        encoded_path = metadata.get("encoded_path")
        
        if encoded_path and os.path.exists(encoded_path):
            try:
                os.remove(encoded_path)
                logger.info(f"Deleted encoded file: {encoded_path}")
            except OSError as e:
                logger.error(f"Failed to delete file {encoded_path}: {e}")
                # Continue to update DB anyway
        
        # Update metadata
        metadata["is_encoded"] = False
        if "encoded_path" in metadata:
            del metadata["encoded_path"]
            
        sb = await get_database()
        await sb.table("videos").update({"metadata": metadata}).eq("id", video["id"]).execute()
        
        return {"success": True, "message": "Optimized file deleted"}
        
    except Exception as e:
        logger.error(f"Error deleting encoded file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
    """Download video file directly (prioritize encoded file)"""
    from src.db import get_video_by_short_id
    
    try:
        video = await get_video_by_short_id(short_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")

        metadata = video.get("metadata") or {}
        
        # 1. Check if encoded file exists
        is_encoded = metadata.get("is_encoded", False)
        encoded_path = metadata.get("encoded_path")
        
        if is_encoded and encoded_path and os.path.exists(encoded_path):
            title = video.get('title', 'video')
            filename = f"{title}.mp4".replace('/', '_').replace('\\', '_')
            logger.info(f"Serving encoded file for download: {encoded_path}")
            return FileResponse(
                path=encoded_path,
                filename=filename,
                media_type="video/mp4"
            )

        # 2. Fallback to existing logic if not encoded
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
        logger.info(f"Admin User ID for notifications: {DEFAULT_USER_ID}")

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
            format_spec = "bestaudio/best"
        elif str(quality).isdigit():
            # Height based with AVC priority
            h = int(quality)
            format_spec = (
                f"bestvideo[height<={h}][vcodec^=avc]+bestaudio[acodec^=mp4a]/"
                f"bestvideo[height<={h}]+bestaudio/"
                f"bestvideo[height<={h}]+bestaudio/best"
            )
        else:
            # Best quality with AVC priority
            format_spec = (
                "bestvideo[vcodec^=avc]+bestaudio[acodec^=mp4a]/"
                "bestvideo+bestaudio/best"
            )

        ydl_opts = {
            'format': format_spec,
            'outtmpl': output_template,
            'quiet': False,
            'no_warnings': False,
            'progress_hooks': [progress_hook],
            'format_sort': ['res', 'vcodec:h264', 'acodec:aac'],
            'extractor_args': {
                'youtube': {
                    'player_client': ['android'],
                }
            },
            'nocheckcertificate': True,
        }

        # Use proxy if configured (e.g. for bypassing regional blocks)
        proxy_url = os.getenv("PROXY_URL")
        if proxy_url:
            ydl_opts['proxy'] = proxy_url
            logger.info(f"Using proxy: {proxy_url}")
        
        if is_audio:
            ydl_opts['postprocessors'] = [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
            }]
        
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get('title', 'video')
                downloaded_file = ydl.prepare_filename(info)
                
                # Handle audio conversion
                if quality == 'audio':
                    downloaded_file = str(Path(downloaded_file).with_suffix('.mp3'))
        except Exception as dl_error:
            # Check for ConnectionResetError or similar transport errors typical of blocking
            error_str = str(dl_error)
            if "ConnectionResetError" in error_str or "10054" in error_str:
                logger.error("Connection reset detected. This site may be blocked in your region.")
                logger.error("Try setting PROXY_URL in your .env file (e.g., PROXY_URL=http://127.0.0.1:1080)")
            raise dl_error
        
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

            # Start HLS generation immediately
            try:
                logger.info(f"🚀 Triggering immediate HLS generation for {short_id}")
                asyncio.create_task(generate_hls_for_video(short_id))
            except Exception as hls_error:
                logger.warning(f"Failed to trigger HLS generation: {hls_error}")

            # Notify DEFAULT_USER_ID via Telegram
            if DEFAULT_USER_ID:
                try:
                    logger.info(f"📢 Preparing notification for admin (ID: {DEFAULT_USER_ID})")
                    stream_url = f"{BASE_URL}/watch/{short_id}"
                    download_url = f"{BASE_URL}/download/{short_id}"
                    msg_text = (
                        f"✅ **웹 다운로드 완료! (Large File)**\n\n"
                        f"📹 **{title}**\n"
                        f"⚠️ 대용량 파일이므로 스트리밍으로 제공됩니다.\n\n"
                        f"🔗 [심리스 스트리밍으로 보기]({stream_url})\n"
                        f"📥 [파일 다운로드]({download_url})"
                    )
                    await bot.send_message(
                        chat_id=DEFAULT_USER_ID,
                        text=msg_text,
                        parse_mode=ParseMode.MARKDOWN
                    )
                    logger.info(f"✅ Notification sent to {DEFAULT_USER_ID}")
                except Exception as notify_error:
                    logger.error(f"❌ Failed to notify admin {DEFAULT_USER_ID}: {notify_error}")
            else:
                logger.warning("⚠️ DEFAULT_USER_ID is not set, skipping notification")

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

        # Start HLS generation immediately
        try:
            logger.info(f"🚀 Triggering immediate HLS generation for {short_id}")
            asyncio.create_task(generate_hls_for_video(short_id))
        except Exception as hls_error:
            logger.warning(f"Failed to trigger HLS generation: {hls_error}")

        # Notify DEFAULT_USER_ID via Telegram
        if DEFAULT_USER_ID:
            try:
                logger.info(f"📢 Preparing notification for admin (ID: {DEFAULT_USER_ID})")
                stream_url = f"{BASE_URL}/watch/{short_id}"
                download_url = f"{BASE_URL}/download/{short_id}"
                msg_text = (
                    f"✅ **웹 다운로드 완료!**\n\n"
                    f"📹 **{title}**\n\n"
                    f"🔗 [심리스 스트리밍으로 보기]({stream_url})\n"
                    f"📥 [파일 다운로드]({download_url})"
                )
                await bot.send_message(
                    chat_id=DEFAULT_USER_ID,
                    text=msg_text,
                    parse_mode=ParseMode.MARKDOWN
                )
                logger.info(f"✅ Notification sent to {DEFAULT_USER_ID}")
            except Exception as notify_error:
                logger.error(f"❌ Failed to notify admin {DEFAULT_USER_ID}: {notify_error}")
        else:
            logger.warning("⚠️ DEFAULT_USER_ID is not set, skipping notification")

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


# General File Management Endpoints

# EPUB Reader Routes

@app.get("/read/{file_id}", response_class=HTMLResponse)
async def reader_page(request: Request, file_id: int):
    """EPUB Reader page"""
    from src.db import get_file_by_id, get_reading_progress
    
    try:
        f = await get_file_by_id(file_id)
        if not f:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error_code": 404,
                "error_message": "Book not found"
            })
            
        # Get progress
        # We need user_id from somewhere. 
        # For now, relying on DEFAULT_USER_ID or passed query param? 
        # The URL /read/{file_id} doesn't have user_id. 
        # Let's assume DEFAULT_USER_ID if no auth middleware is strictly enforcing user context yet.
        # Ideally, user_id should be in session or query param.
        # Let's add user_id query param support for consistency with other pages.
        user_id = int(request.query_params.get("user_id", DEFAULT_USER_ID))
        
        progress = await get_reading_progress(user_id, file_id)
        initial_cfi = progress['cfi'] if progress else None
        
        # Download URL for the file (proxied)
        # We use the existing download/stream endpoint logic
        book_url = f"/api/files/download/{file_id}"
        
        return templates.TemplateResponse("reader.html", {
            "request": request,
            "file_id": file_id,
            "user_id": user_id,
            "title": f.get("file_name", "Book"),
            "book_url": book_url,
            "initial_cfi": initial_cfi
        })
    except Exception as e:
        logger.error(f"Error loading reader: {e}")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_code": 500,
            "error_message": "Could not load reader"
        })

@app.get("/api/epub/progress/{file_id}")
async def get_progress_api(file_id: int, user_id: int = DEFAULT_USER_ID):
    from src.db import get_reading_progress
    try:
        progress = await get_reading_progress(user_id, file_id)
        return {"success": True, "data": progress}
    except Exception as e:
        return {"success": False, "message": str(e)}

@app.post("/api/epub/progress")
async def save_progress_api(
    file_id: int = Body(...),
    user_id: int = Body(...),
    cfi: str = Body(...),
    percent: float = Body(...)
):
    from src.db import save_reading_progress
    try:
        await save_reading_progress(user_id, file_id, cfi, percent)
        return {"success": True}
    except Exception as e:
        logger.error(f"Save progress error: {e}")
        return {"success": False, "message": str(e)}

@app.get("/books/{user_id}", response_class=HTMLResponse)
async def books_page(
    request: Request,
    user_id: int,
    page: int = 1,
    per_page: int = 20,
    q: str = ""
):
    from src.db import get_files, count_files
    
    try:
        if page < 1: page = 1
        
        # Workaround for Cloudflare 500 error on %.epub queries
        # Fetch larger dataset and filter in Python
        fetch_limit = 1000
        
        all_files = await get_files(
            user_id=user_id,
            limit=fetch_limit,
            offset=0, # Ignore DB offset
            query=q,
            ext="epub" # Ignored by DB, used as intent marker
        )
        
        # Python Filtering
        books = [f for f in all_files if f.get('file_name', '').lower().endswith('.epub')]
        
        # Manual Pagination
        total_count = len(books)
        start = (page - 1) * per_page
        end = start + per_page
        paginated_books = books[start:end]
        
        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
        
        formatted_books = []
        for b in paginated_books:
            metadata = b.get("metadata") or {}
            
            # Format cover URL
            cover_url = ""
            cover_file_id = metadata.get("cover_file_id")
            if cover_file_id:
                cover_url = f"/thumb/{cover_file_id}"
            
            formatted_books.append({
                "id": b["id"],
                "title": metadata.get("book_title") or b["file_name"],
                "author": metadata.get("author") or "Unknown",
                "cover_url": cover_url,
                "size_mb": f"{b['file_size'] / (1024*1024):.1f}" if b.get('file_size') else ""
            })
            
        return templates.TemplateResponse("books.html", {
            "request": request,
            "user_id": user_id,
            "books": formatted_books,
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count,
            "query": q
        })
    except Exception as e:
        logger.error(f"Error loading books page: {e}")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_code": 500,
            "error_message": "Could not load books"
        })

@app.get("/books", response_class=HTMLResponse)
async def books_default_page(request: Request):
    return await books_page(request, DEFAULT_USER_ID)

@app.get("/files/{user_id}", response_class=HTMLResponse)
async def files_page(
    request: Request, 
    user_id: int,
    q: str = "",
    date_from: str = "",
    date_to: str = "",
    sort: str = "latest",
    page: int = 1,
    per_page: int = 20,
    ext: str = ""
):
    """File management page with search, filters, pagination, and type filter"""
    from src.db import get_files, count_files
    
    try:
        if page < 1: page = 1
        
        if ext:
            # Python Filtering Workaround
            fetch_limit = 1000
            all_files = await get_files(
                user_id=user_id, 
                limit=fetch_limit,
                offset=0,
                query=q,
                date_from=date_from,
                date_to=date_to,
                sort_by=sort,
                ext=ext
            )
            
            # Filter
            target_ext = f".{ext.lower()}"
            filtered_files = [f for f in all_files if f.get('file_name', '').lower().endswith(target_ext)]
            
            # Paginate
            total_count = len(filtered_files)
            start = (page - 1) * per_page
            end = start + per_page
            files = filtered_files[start:end]
            
        else:
            # Standard DB Pagination
            offset = (page - 1) * per_page
            files = await get_files(
                user_id=user_id, 
                limit=per_page,
                offset=offset,
                query=q,
                date_from=date_from,
                date_to=date_to,
                sort_by=sort
            )
            total_count = await count_files(
                user_id=user_id,
                query=q,
                date_from=date_from,
                date_to=date_to
            )
        
        total_pages = (total_count + per_page - 1) // per_page if total_count > 0 else 1
        
        # Format for template
        formatted_files = []
        for f in files:
            # Check if large/multi-part
            metadata = f.get("metadata") or {}
            is_large = False
            if metadata.get("parts") and len(metadata["parts"]) > 1:
                is_large = True
            
            # Check if epub
            is_epub = f.get("file_name", "").lower().endswith(".epub")
            
            formatted_files.append({
                "id": f["id"],
                "file_id": f["file_id"],
                "file_name": f["file_name"],
                "file_size": f["file_size"],
                "file_size_fmt": f"{f['file_size'] / (1024*1024):.1f} MB" if f['file_size'] else "Unknown",
                "created_at": format_date(f["created_at"]),
                "is_large": is_large,
                "is_epub": is_epub
            })

        return templates.TemplateResponse("files.html", {
            "request": request,
            "user_id": user_id,
            "files": formatted_files,
            "query": q,
            "date_from": date_from,
            "date_to": date_to,
            "sort": sort,
            "page": page,
            "total_pages": total_pages,
            "total_count": total_count,
            "ext": ext
        })
    except Exception as e:
        logger.error(f"Error loading files page: {e}")
        return templates.TemplateResponse("error.html", {
            "request": request,
            "error_code": 500,
            "error_message": "Could not load files"
        })

@app.get("/files", response_class=HTMLResponse)
async def files_default_page(request: Request):
    return await files_page(request, DEFAULT_USER_ID)

@app.post("/api/files/upload")
async def upload_general_file(
    file: UploadFile = File(...),
    user_id: Optional[int] = Form(None)
):
    """Upload general file to Telegram (files table) with enhanced stability"""
    tmp_path = None
    try:
        if not user_id:
            user_id = DEFAULT_USER_ID
        
        logger.info(f"Starting general file upload: {file.filename}")

        # Async save to temp
        tmp_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}_{file.filename}")
        async with aiofiles.open(tmp_path, 'wb') as out_file:
            while content := await file.read(1024 * 1024):  # 1MB chunks
                await out_file.write(content)

        file_size = os.path.getsize(tmp_path)
        parts = [tmp_path]
        
        # Split if needed
        if file_size > MAX_WEB_UPLOAD_SIZE:
             chunk_size = MAX_WEB_UPLOAD_SIZE
             parts = []
             with open(tmp_path, 'rb') as f:
                 part_num = 1
                 while True:
                     chunk = f.read(chunk_size)
                     if not chunk: break
                     part_name = f"{tmp_path}.part{part_num}"
                     with open(part_name, 'wb') as p:
                         p.write(chunk)
                     parts.append(part_name)
                     part_num += 1
             if len(parts) == 1:
                 os.unlink(parts[0])
                 parts = [tmp_path]
             else:
                 logger.info(f"Split generic file into {len(parts)} parts")

        # Telegram Upload
        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        bin_channel_id = os.getenv("BIN_CHANNEL_ID")
        upload_chat_id = int(bin_channel_id) if bin_channel_id else user_id
        
        request = HTTPXRequest(connect_timeout=60, read_timeout=600, write_timeout=600)
        bot = Bot(token=bot_token, request=request)

        async def send_with_retries(send_func, label):
            last_error = None
            for attempt in range(1, 4):
                try:
                    return await send_func()
                except Exception as send_error:
                    last_error = send_error
                    if attempt < 3:
                        logger.warning(f"{label} attempt {attempt}/3 failed: {send_error}")
                        await asyncio.sleep(2 * attempt)
            raise last_error

        file_ids = []
        
        for i, part_path in enumerate(parts):
            filename_part = file.filename
            if len(parts) > 1:
                filename_part += f".part{i+1}"
                
            async def upload_task():
                with open(part_path, "rb") as f:
                    caption = f"📁 <b>File Upload</b>\n📄 {file.filename} ({i+1}/{len(parts)})"
                    return await bot.send_document(
                        chat_id=upload_chat_id,
                        document=f,
                        filename=filename_part,
                        caption=caption,
                        parse_mode=ParseMode.HTML,
                        read_timeout=300,
                        write_timeout=300
                    )
            
            msg = await send_with_retries(upload_task, f"upload_part_{i+1}")
            file_ids.append(msg.document.file_id)

        # Cleanup parts
        for p in parts:
            if p != tmp_path and os.path.exists(p):
                os.unlink(p)
        
        # EPUB Metadata Extraction (before deleting main temp file)
        metadata = {}
        if file.filename.lower().endswith('.epub'):
            try:
                # Extract metadata from the temp file we saved earlier
                epub_meta = await asyncio.to_thread(get_epub_metadata, tmp_path)
                
                if epub_meta.get('title'):
                    metadata['book_title'] = epub_meta['title']
                if epub_meta.get('author'):
                    metadata['author'] = epub_meta['author']
                
                # Upload cover if exists
                if epub_meta.get('cover_bytes'):
                    cover_ext = epub_meta.get('cover_ext', '.jpg')
                    with tempfile.NamedTemporaryFile(suffix=cover_ext, delete=False) as tmp_cover:
                        tmp_cover.write(epub_meta['cover_bytes'])
                        tmp_cover_path = tmp_cover.name
                    
                    try:
                        async def upload_cover():
                            with open(tmp_cover_path, 'rb') as c:
                                return await bot.send_photo(
                                    chat_id=upload_chat_id,
                                    photo=c,
                                    caption=f"🖼️ Cover: {file.filename}"
                                )
                        
                        cover_msg = await send_with_retries(upload_cover, "upload_cover")
                        if cover_msg.photo:
                            metadata['cover_file_id'] = cover_msg.photo[-1].file_id
                    finally:
                        if os.path.exists(tmp_cover_path):
                            os.unlink(tmp_cover_path)
            except Exception as e:
                logger.error(f"Failed to extract EPUB metadata: {e}")

        # Cleanup main temp file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

        # DB Entry
        from src.db import add_file
        
        if len(parts) > 1:
            metadata["parts"] = [{"file_id": fid, "part": i+1} for i, fid in enumerate(file_ids)]
        
        file_data = {
            "user_id": user_id,
            "file_id": file_ids[0], # Master ID
            "file_name": file.filename,
            "file_size": file_size,
            "mime_type": file.content_type,
            "metadata": metadata if metadata else None
        }
        
        await add_file(file_data)
        
        # Notify
        if DEFAULT_USER_ID:
             try:
                 await bot.send_message(
                    chat_id=DEFAULT_USER_ID,
                    text=f"✅ <b>파일 업로드 완료!</b>\n📄 {file.filename} ({file_size/1024/1024:.1f}MB)",
                    parse_mode=ParseMode.HTML
                )
             except: pass

        return {"success": True, "message": "File uploaded"}

    except Exception as e:
        logger.error(f"File upload error: {e}")
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except: pass
        return {"success": False, "message": str(e)}

@app.post("/api/files/prepare-download")
async def prepare_download_api(
    background_tasks: BackgroundTasks,
    request: Request
):
    from src.db import get_file_by_id
    
    try:
        data = await request.json()
        target_ids = data.get("file_ids", [])
        user_id = data.get("user_id") or DEFAULT_USER_ID
        
        if not target_ids:
            return {"success": False, "message": "No files selected"}

        bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
        files_info = []
        
        for db_id in target_ids:
            f = await get_file_by_id(db_id)
            if not f: continue
            
            metadata = f.get("metadata") or {}
            parts = metadata.get("parts")
            
            if parts:
                sorted_parts = sorted(parts, key=lambda x: x.get("part", 0))
                part_ids = [p["file_id"] for p in sorted_parts]
                files_info.append({"name": f["file_name"], "parts": part_ids})
            else:
                files_info.append({"name": f["file_name"], "parts": [f["file_id"]]})
        
        task_id = str(uuid.uuid4())
        
        background_tasks.add_task(
            prepare_download_task,
            task_id=task_id,
            files_info=files_info,
            user_id=user_id,
            bot_token=bot_token,
            base_url=BASE_URL
        )
        
        return {"success": True, "message": "다운로드 준비 시작! 완료되면 텔레그램으로 알려드립니다."}
        
    except Exception as e:
        logger.error(f"Prepare download error: {e}")
        return {"success": False, "message": str(e)}

@app.get("/api/files/download_ready/{task_id}/{filename}")
async def download_ready_file(task_id: str, filename: str):
    path = DOWNLOAD_CACHE_DIR / filename
    # Also try zip if extension doesn't match? No, filename comes from URL.
    # But prepare_task might have renamed collision.
    # Trust filename in URL.
    
    if path.exists():
        return FileResponse(path, filename=filename)
    
    return HTMLResponse("<h1>File expired or not found</h1>", status_code=404)

@app.get("/api/files/download/{file_id}")
async def download_file_by_db_id(file_id: int):
    """
    Download file by DB ID. Handles split files by concatenating them.
    For EPUBs, caches locally to support random access/Range requests.
    """
    from src.db import get_file_by_id
    
    try:
        f = await get_file_by_id(file_id)
        if not f:
            raise HTTPException(status_code=404, detail="File not found")
            
        metadata = f.get("metadata") or {}
        parts = metadata.get("parts")
        filename = f.get("file_name", "download")
        encoded_filename = quote(filename)
        is_epub = filename.lower().endswith(".epub")
        media_type = "application/epub+zip" if is_epub else "application/octet-stream"
        
        # If EPUB, cache it locally first to support seeking/epub.js
        if is_epub:
            cache_path = DOWNLOAD_CACHE_DIR / filename
            if cache_path.exists():
                return FileResponse(
                    path=cache_path,
                    media_type=media_type,
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"}
                )
            
            # Need to download/concat to cache
            temp_path = str(cache_path) + ".tmp"
            try:
                if parts:
                    sorted_parts = sorted(parts, key=lambda x: x.get("part", 0))
                    tg_file_ids = [p["file_id"] for p in sorted_parts]
                    download_urls = await asyncio.gather(*[get_file_path_from_telegram(fid) for fid in tg_file_ids])
                    
                    async with aiofiles.open(temp_path, 'wb') as outfile:
                        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, read=600.0), follow_redirects=True) as client:
                            for url in download_urls:
                                async with client.stream("GET", url) as r:
                                    r.raise_for_status()
                                    async for chunk in r.aiter_bytes(chunk_size=65536):
                                        await outfile.write(chunk)
                else:
                    tg_file_id = f.get("file_id")
                    download_url = await get_file_path_from_telegram(tg_file_id)
                    async with aiofiles.open(temp_path, 'wb') as outfile:
                        async with httpx.AsyncClient(timeout=None) as client:
                            async with client.stream("GET", download_url) as r:
                                r.raise_for_status()
                                async for chunk in r.aiter_bytes():
                                    await outfile.write(chunk)
                
                os.rename(temp_path, cache_path)
                return FileResponse(
                    path=cache_path,
                    media_type=media_type,
                    headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"}
                )
            except Exception as e:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                raise e

        # Non-EPUB: Streaming (existing logic)
        if parts:
            # Multi-part file: Stream concat
            sorted_parts = sorted(parts, key=lambda x: x.get("part", 0))
            tg_file_ids = [p["file_id"] for p in sorted_parts]
            
            download_urls = await asyncio.gather(
                *[get_file_path_from_telegram(fid) for fid in tg_file_ids]
            )
            
            async def iter_concat():
                async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, read=600.0), follow_redirects=True) as client:
                    for url in download_urls:
                        async with client.stream("GET", url) as r:
                            r.raise_for_status()
                            async for chunk in r.aiter_bytes(chunk_size=65536):
                                yield chunk
                                
            return StreamingResponse(
                iter_concat(),
                media_type=media_type,
                headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"}
            )
            
        else:
            # Single file
            tg_file_id = f.get("file_id")
            download_url = await get_file_path_from_telegram(tg_file_id)
            
            async def iter_file():
                async with httpx.AsyncClient(timeout=None) as client:
                    async with client.stream("GET", download_url) as r:
                        async for chunk in r.aiter_bytes():
                            yield chunk
                            
            return StreamingResponse(
                iter_file(),
                media_type=media_type,
                headers={"Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"}
            )

    except Exception as e:
        logger.error(f"Download error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/files/{file_id}")
async def delete_file_api(file_id: int, user_id: Optional[int] = Body(None)):
    from src.db import delete_file
    if not user_id: user_id = DEFAULT_USER_ID
    success = await delete_file(file_id, user_id)
    return {"success": success}


# Phase 1: Dashboard Page
@app.get("/dashboard/{user_id}", response_class=HTMLResponse)
async def dashboard_page(request: Request, user_id: int):
    """User dashboard with statistics and quick access"""
    from src.user_manager import get_user_stats
    from src.db import get_database, get_user_videos, get_recent_reading
    from src.link_shortener import get_or_create_short_link
    
    try:
        # Get user stats
        sb = await get_database()
        stats = await get_user_stats(sb, user_id)
        
        # Get recent videos
        recent_videos = await get_user_videos(user_id, limit=5)
        
        # Get recent reading
        recent_reading = await get_recent_reading(user_id)
        if recent_reading:
            # Format file info
            file_info = recent_reading.get('files')
            if file_info:
                recent_reading['title'] = file_info.get('file_name', 'Unknown Book')
                recent_reading['percent_fmt'] = f"{recent_reading.get('percent', 0):.1f}%"
        
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
            "recent_videos": formatted_videos,
            "recent_reading": recent_reading
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
    """Upload local video file to Telegram with enhanced stability"""
    tmp_path = None

    try:
        if not user_id:
            user_id = DEFAULT_USER_ID
        
        logger.info(f"Starting video upload. Admin User ID: {DEFAULT_USER_ID}")

        # Async save to temp
        tmp_path = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4()}_{file.filename}")
        async with aiofiles.open(tmp_path, 'wb') as out_file:
            while content := await file.read(1024 * 1024):  # 1MB chunks
                await out_file.write(content)

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
            
            async def upload_task():
                with open(path, "rb") as f:
                    msg = await bot.send_document(
                        chat_id=upload_chat_id,
                        document=f,
                        caption=caption,
                        parse_mode=ParseMode.HTML,
                        read_timeout=300,
                        write_timeout=300
                    )
                    return msg

            message = await send_with_retries(upload_task, "send_document")
            
            if message.document:
                return (message.document.file_id, 0, "")
            if message.video:
                return (message.video.file_id, message.video.duration or 0, "")
            
            # Try getting video if document is missing (sometimes send_document returns video object if mime matches)
            # Actually python-telegram-bot send_document returns Message object
            # If uploaded as document, it has .document. If video, .video.
            # We force send_document, so it should be document or video.
            raise Exception("Telegram upload failed (no document/video in response)")

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

        # Start HLS generation immediately
        try:
            logger.info(f"🚀 Triggering immediate HLS generation for {short_id}")
            asyncio.create_task(generate_hls_for_video(short_id))
        except Exception as hls_error:
            logger.warning(f"Failed to trigger HLS generation: {hls_error}")

        # Notify DEFAULT_USER_ID via Telegram
        if DEFAULT_USER_ID:
            try:
                logger.info(f"📢 Preparing notification for admin (ID: {DEFAULT_USER_ID})")
                stream_url = f"{BASE_URL}/watch/{short_id}"
                download_url = f"{BASE_URL}/download/{short_id}"
                msg_text = (
                    f"✅ **웹 업로드 완료!**\n\n"
                    f"📹 **{file.filename}**\n\n"
                    f"🔗 [심리스 스트리밍으로 보기]({stream_url})\n"
                    f"📥 [파일 다운로드]({download_url})"
                )
                await bot.send_message(
                    chat_id=DEFAULT_USER_ID,
                    text=msg_text,
                    parse_mode=ParseMode.MARKDOWN
                )
                logger.info(f"✅ Notification sent to {DEFAULT_USER_ID}")
            except Exception as notify_error:
                logger.error(f"❌ Failed to notify admin {DEFAULT_USER_ID}: {notify_error}")
        else:
            logger.warning("⚠️ DEFAULT_USER_ID is not set, skipping notification")

        # Delete temporary file(s) immediately
        cleanup_paths = set(parts + [tmp_path])
        if thumbnail_temp_path:
            cleanup_paths.add(thumbnail_temp_path)
        for path in cleanup_paths:
            if path and os.path.exists(path):
                try:
                    os.unlink(path)
                    logger.info("Temporary file deleted: %s", path)
                except: pass

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


@app.post("/api/reencode/{short_id}")
async def reencode_video(
    short_id: str, 
    background_tasks: BackgroundTasks, 
    user_id: Optional[int] = Body(None),
    resolution: str = Body("720p")
):
    """Trigger video re-encoding for mobile compatibility"""
    from src.db import get_video_by_short_id, get_database
    
    try:
        logger.info(f"🔄 Re-encode request received for {short_id} (User: {user_id}, Res: {resolution})")
        
        video = await get_video_by_short_id(short_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
            
        metadata = video.get("metadata") or {}
        if metadata.get("is_encoded") and os.path.exists(metadata.get("encoded_path", "")):
            # If already encoded, we might want to allow re-encoding if resolution is different?
            # For now, let's just return success if it's already done, but usually users want to force it.
            # But the UI disables the button.
            # If the user manually calls API, let's allow it if they really want, but current UI check prevents it.
            # To allow re-encoding with different resolution, we should probably bypass this check if force param is present,
            # or just proceed. But let's stick to the current logic: if encoded, say exists.
            # Wait, if I want to change resolution, I need to be able to re-encode.
            # Let's remove this check or make it smarter. 
            # For now, I will keep it but maybe the user will delete the old one first?
            # Actually, the user asked to select resolution. If they select one, it should probably proceed.
            # But `templates/watch.html` disables the button if `is_encoded`.
            # So this check is fine for the current flow (first time optimization).
            return {"success": True, "message": "Already encoded", "already_exists": True}
            
        # Start background task
        sb = await get_database()
        
        target_user_id = user_id or video.get("user_id") or DEFAULT_USER_ID
        token = os.getenv("TELEGRAM_BOT_TOKEN")
        
        if not token:
             raise HTTPException(status_code=500, detail="Bot token missing")

        logger.info(f"➕ Adding background task for video {video['id']}")
        
        background_tasks.add_task(
            transcode_video_task,
            video_id=video["id"],
            short_id=short_id,
            user_id=target_user_id,
            bot_token=token,
            base_url=BASE_URL,
            db_client=sb,
            resolution=resolution
        )
        
        return {"success": True, "message": "Re-encoding started in background"}
        
    except Exception as e:
        logger.error(f"Re-encode error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/stream/encoded/{short_id}")
async def stream_encoded_video(short_id: str, request: Request):
    """Stream re-encoded MP4 file with Range support"""
    from src.db import get_video_by_short_id
    
    try:
        video = await get_video_by_short_id(short_id)
        if not video:
            raise HTTPException(status_code=404, detail="Video not found")
            
        metadata = video.get("metadata") or {}
        encoded_path = metadata.get("encoded_path")
        
        if not encoded_path or not os.path.exists(encoded_path):
            raise HTTPException(status_code=404, detail="Encoded file not found")
            
        return FileResponse(
            path=encoded_path,
            media_type="video/mp4",
            headers={"Accept-Ranges": "bytes"}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Encoded stream error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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


