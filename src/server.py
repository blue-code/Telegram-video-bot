from fastapi import FastAPI, HTTPException, Request, Header, Body, File, UploadFile, Form
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import asyncio
import os
import httpx
import logging
import json
import tempfile
import shutil
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
MAX_WEB_UPLOAD_SIZE = 30 * 1024 * 1024  # 30MB safety buffer for Bot API limits.

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


# Mock DB or Bot interaction for now
async def get_file_path_from_telegram(file_id):
    """
    In a real scenario, we would need to:
    1. Get file_path from getFile API using bot token
    2. Construct download URL: https://api.telegram.org/file/bot<token>/<file_path>
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="Bot token not valid")
        
    async with httpx.AsyncClient() as client:
        # 1. Get File Path
        resp = await client.get(f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}")
        data = resp.json()
        
        if not data.get("ok"):
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
    from src.db import get_video_by_short_id
    
    try:
        video = await get_video_by_short_id(short_id)
        
        if not video:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error_code": 404,
                "error_message": "Video not found"
            })
        
        return templates.TemplateResponse("watch.html", {
            "request": request,
            "short_id": short_id,
            "file_id": video.get('file_id', ''),
            "video_title": video.get('title', 'Unknown'),
            "view_count": video.get('views', 0),
            "duration": format_duration(video.get('duration', 0)),
            "upload_date": format_date(video.get('created_at'))
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
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("GET", download_url) as r:
                    async for chunk in r.aiter_bytes():
                        yield chunk

        return StreamingResponse(iter_file(), media_type="video/mp4")
        
    except Exception as e:
        logging.error(f"Streaming error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Gallery Page
@app.get("/gallery/{user_id}", response_class=HTMLResponse)
async def gallery_page(request: Request, user_id: int):
    """Gallery page showing user's videos"""
    from src.db import get_user_videos
    
    try:
        videos = await get_user_videos(user_id, limit=100)
        
        formatted_videos = []
        for video in videos:
            # Try to get short_id from shared_links if available
            short_id = video.get('short_id', '')
            if not short_id:
                # Fall back to file_id
                short_id = video.get('file_id', '')
            
            formatted_videos.append({
                'short_id': short_id,
                'title': video.get('title', 'Unknown'),
                'thumbnail': video.get('thumbnail', ''),
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
        success = await delete_video_by_id(video_id, user_id)
        
        if success:
            return {"success": True, "message": "Video deleted"}
        else:
            raise HTTPException(status_code=404, detail="Video not found or unauthorized")
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
    
    try:
        # Get user stats
        sb = await get_database()
        stats = await get_user_stats(sb, user_id)
        
        # Get recent videos
        recent_videos = await get_user_videos(user_id, limit=5)
        
        # Format videos
        formatted_videos = []
        for video in recent_videos:
            formatted_videos.append({
                'short_id': video.get('short_id', video.get('file_id')),
                'title': video.get('title', 'Unknown'),
                'thumbnail': video.get('thumbnail', ''),
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
    from src.db import search_videos
    
    try:
        if not user_id:
            user_id = DEFAULT_USER_ID
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
            formatted_results.append({
                'short_id': video.get('short_id', video.get('file_id')),
                'title': video.get('title', 'Unknown'),
                'thumbnail': video.get('thumbnail', ''),
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

        file_size = os.path.getsize(tmp_path)
        if file_size > MAX_WEB_UPLOAD_SIZE:
            logger.info(
                "File exceeds limit (%.1fMB), splitting into parts.",
                file_size / (1024 * 1024)
            )
            from src.splitter import split_video
            parts = await split_video(tmp_path, MAX_WEB_UPLOAD_SIZE)
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

        async def send_video(path, caption):
            with open(path, "rb") as video_file:
                return await bot.send_video(
                    chat_id=upload_chat_id,
                    video=video_file,
                    caption=caption,
                    parse_mode=ParseMode.HTML,
                    supports_streaming=True
                )

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
            try:
                message = await send_with_retries(
                    lambda: send_video(path, caption),
                    "send_video"
                )
                if not message.video:
                    raise Exception("Telegram did not return video metadata")
                return (
                    message.video.file_id,
                    message.video.duration or 0,
                    message.video.thumbnail.file_id
                    if message.video.thumbnail else ""
                )
            except Exception as upload_error:
                logger.warning(
                    "send_video failed for %s: %s",
                    part_label,
                    upload_error
                )
                message = await send_with_retries(
                    lambda: send_document(path, caption),
                    "send_document"
                )
                if not message.document:
                    raise Exception("Telegram upload failed")
                return (message.document.file_id, 0, "")

        # Save metadata to database
        from src.db import get_database
        from src.link_shortener import create_short_link
        sb = await get_database()

        async def save_video_entry(file_id, title, duration, thumbnail):
            video_data = {
                "file_id": file_id,
                "title": title,
                "duration": duration,
                "thumbnail": thumbnail,
                "user_id": user_id,
                "url": None  # No URL for local uploads
            }
            video_id = None
            try:
                result = await sb.table("videos").insert(video_data).execute()
                if result.data:
                    video_id = result.data[0].get("id")
                else:
                    logger.warning("Video insert returned no data: %s", result)
            except Exception as db_error:
                logger.error("Video metadata insert failed: %s", db_error)

            if video_id is None:
                try:
                    lookup = await sb.table("videos").select("id").eq(
                        "file_id", file_id
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

            short_id = await create_short_link(sb, file_id, video_id, user_id)
            return short_id

        short_id = None
        part_links = []
        total_parts = len(parts)

        for index, part_path in enumerate(parts, start=1):
            if total_parts == 1:
                part_title = file.filename
            else:
                part_title = (
                    f"{Path(file.filename).stem} (Part {index}/{total_parts})"
                    f"{Path(file.filename).suffix}"
                )

            logger.info(
                "Uploading %s to Telegram chat_id=%s...",
                part_title,
                upload_chat_id
            )
            file_id, duration, thumbnail = await upload_part(
                part_path,
                part_title
            )
            part_short_id = await save_video_entry(
                file_id,
                part_title,
                duration,
                thumbnail
            )
            part_links.append({
                "part": index,
                "short_id": part_short_id,
                "file_id": file_id
            })
            if short_id is None:
                short_id = part_short_id

        logger.info("Upload successful! parts=%s", total_parts)

        # Delete temporary file(s) immediately
        for path in set(parts + [tmp_path]):
            if path and os.path.exists(path):
                os.unlink(path)
                logger.info("Temporary file deleted: %s", path)

        message = (
            "✅ Uploaded to Telegram successfully!"
            if total_parts == 1
            else f"✅ Uploaded {total_parts} parts to Telegram successfully!"
        )

        return {
            "success": True,
            "short_id": short_id,
            "filename": file.filename,
            "file_id": part_links[0]["file_id"] if part_links else None,
            "parts": part_links,
            "message": message
        }

    except Exception as e:
        logger.error("File upload error: %s", e)

        # Cleanup temporary file on error
        paths_to_cleanup = set()
        if tmp_path:
            paths_to_cleanup.add(tmp_path)
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

        return {
            "success": False,
            "message": str(e)
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
        
        if not video or video.get('user_id') != user_id:
            return templates.TemplateResponse("error.html", {
                "request": request,
                "error_code": 403,
                "error_message": "Access denied"
            })
        
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
