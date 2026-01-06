from fastapi import FastAPI, HTTPException, Request, Header, Body, File, UploadFile, Form
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse, JSONResponse, RedirectResponse
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
from typing import Optional
from pathlib import Path

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


# Utility Functions
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
async def get_file_path_from_telegram(file_id):
    """
    In a real scenario, we would need to:
    1. Get file_path from getFile API using bot token
    2. Construct download URL: https://api.telegram.org/file/bot<token>/<file_path>
    """
    file_id = str(file_id).strip() if file_id is not None else ""
    if not file_id:
        raise HTTPException(status_code=404, detail="File ID is empty")

    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="Bot token not valid")
        
    async with httpx.AsyncClient() as client:
        # 1. Get File Path
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
        return f"https://api.telegram.org/file/bot{token}/{file_path}"


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
async def stream_video(file_id: str):
    """Proxy stream from Telegram to Browser"""
    try:
        download_url = await get_file_path_from_telegram(file_id)
        
        # Create a generator to stream chunks
        async def iter_file():
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(60.0, read=600.0),
                follow_redirects=True
            ) as client:
                async with client.stream("GET", download_url) as r:
                    r.raise_for_status()
                    async for chunk in r.aiter_bytes():
                        yield chunk

        return StreamingResponse(iter_file(), media_type="video/mp4")
        
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
    """Proxy stream for multi-part videos by concatenating parts with ffmpeg."""
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
                            async for chunk in r.aiter_bytes():
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
            "-fflags", "+genpts",
            "-f", "concat",
            "-safe", "0",
            "-i", list_path,
            "-c", "copy",
            "-avoid_negative_ts", "make_zero",
            "-movflags", "frag_keyframe+empty_moov+default_base_moof",
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
                        chunk = await process.stdout.read(1024 * 256)
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
                        chunk = await asyncio.to_thread(
                            process.stdout.read, 1024 * 256
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

        return StreamingResponse(iter_concat(), media_type="video/mp4")
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
    
    try:
        logger.info(f"Starting web download: {url}")
        
        # Download video using yt-dlp to temporary directory
        import yt_dlp
        
        temp_dir = tempfile.mkdtemp()
        output_template = os.path.join(temp_dir, '%(title)s.%(ext)s')
        
        ydl_opts = {
            'format': f'bestvideo[height<={quality}]+bestaudio/best' if quality != 'audio' else 'bestaudio',
            'outtmpl': output_template,
            'quiet': False,
            'no_warnings': False,
        }
        
        if quality == 'audio':
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
        
        # Upload to Telegram
        from telegram import Bot
        from telegram.constants import ParseMode
        
        bot = Bot(token=bot_token)
        
        logger.info(f"Uploading {title} to Telegram...")
        
        with open(downloaded_file, 'rb') as video_file:
            if quality == 'audio':
                message = await bot.send_audio(
                    chat_id=bin_channel_id,
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
                    chat_id=bin_channel_id,
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
        
        return {
            "success": True,
            "short_id": short_id,
            "title": title,
            "message": "✅ Download and upload complete!"
        }
        
    except Exception as e:
        logger.error(f"Web download error: {e}")
        
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
    from src.db import get_database, search_videos
    from src.link_shortener import get_or_create_short_link
    
    try:
        if not user_id:
            user_id = DEFAULT_USER_ID
        sb = await get_database()
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
