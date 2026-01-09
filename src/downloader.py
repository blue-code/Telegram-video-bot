import asyncio
import os
import yt_dlp
from functools import partial

async def extract_video_info(url: str):
    """
    Asynchronously extracts video information using yt-dlp.
    Does not download the video.
    Returns playlist info if URL is a playlist, otherwise single video info.
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': 'in_playlist',  # For playlists, just get metadata
        # YouTube 403 Forbidden 우회
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
                'skip': ['dash', 'hls'],
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

    # Run blocking yt_dlp call in a separate thread
    loop = asyncio.get_running_loop()
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # Partial allows passing arguments to the function
        func = partial(ydl.extract_info, url, download=False)
        info = await loop.run_in_executor(None, func)
    
    # Check if it's a playlist
    if info.get('_type') == 'playlist' or 'entries' in info:
        entries = list(info.get('entries', []))
        return {
            'is_playlist': True,
            'id': info.get('id'),
            'title': info.get('title', 'Unnamed Playlist'),
            'count': len(entries),
            'entries': [
                {
                    'id': e.get('id'),
                    'title': e.get('title'),
                    'url': e.get('url') or e.get('webpage_url'),
                    'duration': e.get('duration'),
                }
                for e in entries if e
            ],
            'webpage_url': info.get('webpage_url')
        }
    else:
        return {
            'is_playlist': False,
            'id': info.get('id'),
            'title': info.get('title'),
            'duration': info.get('duration'),
            'thumbnail': info.get('thumbnail'),
            'formats': info.get('formats', []),
            'webpage_url': info.get('webpage_url')
        }

async def download_video(url: str, format_id: str, output_path: str, progress_hook=None, quality: str = None):
    """
    Asynchronously downloads a video with a specific format.

    Args:
        url: Video URL
        format_id: Format selector ('best', 'bestaudio', or specific format ID)
        output_path: Download directory
        progress_hook: Progress callback function
        quality: Target height (e.g., '1080', '720') or 'best' for highest quality
    """
    # Determine format string based on quality
    if format_id == 'bestaudio':
        format_str = 'bestaudio/best'
    elif quality and quality != 'best' and quality.isdigit():
        # Height-based quality selection: merge best video (up to height) + best audio
        height = int(quality)
        format_str = f'bestvideo[height<={height}]+bestaudio/best[height<={height}]/best'
    else:
        # Best available quality
        format_str = 'bestvideo+bestaudio/best'

    ydl_opts = {
        'format': format_str,
        'outtmpl': f"{output_path}/%(id)s.%(ext)s",
        'quiet': False, # Debugging: show what's happening
        'no_warnings': False,
        'progress_hooks': [progress_hook] if progress_hook else [],
        'restrictedfilenames': True,
        'merge_output_format': 'mp4',  # Merge video+audio into MP4
        # YouTube 403 Forbidden 우회
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web'],
                'skip': ['dash', 'hls'],
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

    if format_id == 'bestaudio':
        ydl_opts['postprocessors'] = [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }]

    loop = asyncio.get_running_loop()
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # download=True will perform the actual download
        func = partial(ydl.extract_info, url, download=True)
        info = await loop.run_in_executor(None, func)
        
        # 1. Try to get filename from requested_downloads
        if 'requested_downloads' in info and info['requested_downloads']:
            filename = info['requested_downloads'][0].get('filepath')
            if filename and os.path.exists(filename):
                return filename
        
        # 2. Try to get it from '_filename' in info
        filename = info.get('_filename')
        if filename and os.path.exists(filename):
            return filename

        # 3. Handle MP3 conversion case specifically
        if format_id == 'bestaudio':
            # Base name from prepare_filename but with .mp3
            base_filename = ydl.prepare_filename(info)
            mp3_filename = os.path.splitext(base_filename)[0] + ".mp3"
            if os.path.exists(mp3_filename):
                return mp3_filename
            
        # 4. Search directory as a last resort
        if os.path.exists(output_path):
            # Sort by modification time to get the most recent file
            files = [os.path.join(output_path, f) for f in os.listdir(output_path)]
            if files:
                latest_file = max(files, key=os.path.getmtime)
                return latest_file
            
        return ydl.prepare_filename(info)
