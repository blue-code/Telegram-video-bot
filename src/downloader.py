import asyncio
import yt_dlp
from functools import partial

async def extract_video_info(url: str):
    """
    Asynchronously extracts video information using yt-dlp.
    Does not download the video.
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
    }

    # Run blocking yt_dlp call in a separate thread
    loop = asyncio.get_running_loop()
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # Partial allows passing arguments to the function
        func = partial(ydl.extract_info, url, download=False)
        info = await loop.run_in_executor(None, func)
        
    return {
        'id': info.get('id'),
        'title': info.get('title'),
        'duration': info.get('duration'),
        'thumbnail': info.get('thumbnail'),
        'formats': info.get('formats', []),
        'webpage_url': info.get('webpage_url')
    }
