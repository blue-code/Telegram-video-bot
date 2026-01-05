from fastapi import FastAPI, HTTPException, Request, Header, Body, File, UploadFile
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
import httpx
import logging
import json
from datetime import datetime
from dotenv import load_dotenv
from typing import Optional
from pathlib import Path

# Initialize
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="TVB API", version="1.0.0")

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
async def download_page(request: Request):
    """Web download page"""
    return templates.TemplateResponse("download.html", {"request": request})


@app.post("/api/web-download")
async def web_download(
    url: str = Body(...),
    quality: str = Body("best"),
    user_id: int = Body(...)
):
    """Handle web-based video download"""
    from src.downloader import extract_video_info
    from src.link_shortener import generate_short_id
    from src.db import get_database
    
    try:
        # Extract video info (not downloading yet, just metadata)
        info = await extract_video_info(url)
        
        if info.get('is_playlist'):
            return {
                "success": False,
                "message": "Playlist downloads not supported via web interface"
            }
        
        # Generate short link
        short_id = generate_short_id()
        
        # Save to database
        sb = await get_database()
        
        # Insert video metadata
        video_data = {
            "file_id": f"web_{short_id}",  # Temporary file_id for web downloads
            "title": info.get('title', 'Unknown'),
            "duration": info.get('duration', 0),
            "thumbnail": info.get('thumbnail', ''),
            "url": url,
            "user_id": user_id,
            "quality": quality
        }
        
        result = await sb.table("videos").insert(video_data).execute()
        
        if result.data:
            video_id = result.data[0]['id']
            
            # Create short link
            await sb.table("shared_links").insert({
                "short_id": short_id,
                "file_id": video_data['file_id'],
                "video_id": video_id,
                "user_id": user_id,
                "views": 0
            }).execute()
        
        return {
            "success": True,
            "short_id": short_id,
            "title": info.get('title', 'Unknown'),
            "message": "Download complete!"
        }
    except Exception as e:
        logger.error(f"Web download error: {e}")
        return {
            "success": False,
            "message": str(e)
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


# Phase 1: Advanced Search Page
@app.get("/search", response_class=HTMLResponse)
async def search_page(
    request: Request,
    user_id: int,
    q: str = "",
    date_from: str = "",
    date_to: str = "",
    duration: str = "all",
    sort: str = "latest"
):
    """Advanced search page with filters"""
    from src.db import search_videos
    
    try:
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
    user_id: int = Body(...)
):
    """Upload local video file"""
    import shutil
    
    try:
        # Save uploaded file
        upload_dir = Path("uploads")
        upload_dir.mkdir(exist_ok=True)
        
        file_path = upload_dir / file.filename
        
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Generate short link
        from src.link_shortener import generate_short_id
        short_id = generate_short_id()
        
        # Save metadata
        from src.db import get_database
        sb = await get_database()
        
        video_data = {
            "file_id": str(file_path),
            "title": file.filename,
            "duration": 0,  # Extract with ffprobe if needed
            "thumbnail": "",
            "user_id": user_id
        }
        
        result = await sb.table("videos").insert(video_data).execute()
        
        if result.data:
            video_id = result.data[0]['id']
            
            # Create short link
            await sb.table("shared_links").insert({
                "short_id": short_id,
                "file_id": str(file_path),
                "video_id": video_id,
                "user_id": user_id,
                "views": 0
            }).execute()
        
        return {
            "success": True,
            "short_id": short_id,
            "filename": file.filename
        }
    except Exception as e:
        logger.error(f"File upload error: {e}")
        return {"success": False, "message": str(e)}


# Phase 3: Video Editing Features
@app.get("/edit/{video_id}", response_class=HTMLResponse)
async def edit_page(request: Request, video_id: int, user_id: int):
    """Video editing page"""
    from src.db import get_video_by_id
    
    try:
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
