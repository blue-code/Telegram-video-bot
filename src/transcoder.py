import asyncio
import os
import logging
import subprocess
import tempfile
import shutil
import httpx
from pathlib import Path
from datetime import datetime, timedelta
from telegram import Bot
from telegram.request import HTTPXRequest
from telegram.constants import ParseMode

# Logger setup
logger = logging.getLogger(__name__)

# Directory for storing encoded files
ENCODED_CACHE_DIR = Path("encoded_cache")
ENCODED_CACHE_DIR.mkdir(exist_ok=True)

# Constants
CHUNK_SIZE = 64 * 1024  # 64KB

async def download_file(client, url, dest_path):
    """Download a single file from a URL."""
    try:
        async with client.stream("GET", url) as r:
            r.raise_for_status()
            with open(dest_path, "wb") as f:
                async for chunk in r.aiter_bytes(chunk_size=CHUNK_SIZE):
                    f.write(chunk)
        return True
    except Exception as e:
        logger.error(f"Download failed for {url}: {e}")
        return False

async def get_telegram_file_url(bot_token, file_id):
    """Get the download URL for a Telegram file ID."""
    url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        data = resp.json()
        if not data.get("ok"):
            raise Exception(f"Telegram getFile failed: {data}")
        file_path = data["result"]["file_path"]
        return f"https://api.telegram.org/file/bot{bot_token}/{file_path}"

async def transcode_video_task(
    video_id: int,
    short_id: str,
    user_id: int,
    bot_token: str,
    base_url: str,
    db_client
):
    """
    Background task to download, concat (if needed), and transcode video.
    """
    logger.info(f"🚀 Starting transcoding task for video {video_id} (User: {user_id})")
    
    temp_dir = tempfile.mkdtemp()
    input_path = os.path.join(temp_dir, "input.mp4")
    temp_output_path = os.path.join(temp_dir, "encoded.mp4")
    final_output_filename = f"{short_id}_mobile.mp4"
    final_output_path = ENCODED_CACHE_DIR / final_output_filename

    try:
        # 1. Fetch Video Metadata
        resp = await db_client.table("videos").select("*").eq("id", video_id).single().execute()
        video = resp.data
        if not video:
            raise Exception("Video not found in DB")

        title = video.get("title", "Unknown Video")
        metadata = video.get("metadata") or {}
        parts = metadata.get("parts") or []

        # 2. Download Source Video
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, read=600.0)) as client:
            if parts and len(parts) > 1:
                # Multi-part video: Download all parts and concat
                logger.info(f"📥 Downloading {len(parts)} parts for concatenation...")
                part_files = []
                sorted_parts = sorted(parts, key=lambda x: x.get("part", 0))
                
                for idx, part in enumerate(sorted_parts):
                    fid = part.get("file_id")
                    if not fid: continue
                    
                    file_url = await get_telegram_file_url(bot_token, fid)
                    part_path = os.path.join(temp_dir, f"part_{idx}.mp4")
                    
                    success = await download_file(client, file_url, part_path)
                    if not success:
                        raise Exception(f"Failed to download part {idx+1}")
                    part_files.append(part_path)

                # Create concat list
                concat_list_path = os.path.join(temp_dir, "concat.txt")
                with open(concat_list_path, "w", encoding="utf-8") as f:
                    for pf in part_files:
                        f.write(f"file '{pf}'\n")

                # Concat using FFmpeg (copy codec to create single input file)
                logger.info("🔗 Concatenating parts...")
                concat_cmd = [
                    "ffmpeg", "-f", "concat", "-safe", "0",
                    "-i", concat_list_path, "-c", "copy", input_path
                ]
                
                # Use asyncio.to_thread to avoid blocking event loop
                concat_result = await asyncio.to_thread(
                    subprocess.run, 
                    concat_cmd, 
                    check=False, 
                    capture_output=True
                )
                
                if concat_result.returncode != 0:
                     raise Exception(f"Concatenation failed: {concat_result.stderr.decode(errors='replace')}")
                
            else:
                # Single file
                logger.info("📥 Downloading single video file...")
                file_id = video.get("file_id")
                file_url = await get_telegram_file_url(bot_token, file_id)
                success = await download_file(client, file_url, input_path)
                if not success:
                    raise Exception("Failed to download video file")

        # 3. Transcode (Re-encode)
        logger.info("⚙️ Transcoding to H.264/AAC (720p, faststart)...")
        
        # Verify input file
        if os.path.exists(input_path):
            input_size = os.path.getsize(input_path)
            logger.info(f"   Input file size: {input_size} bytes")
            if input_size == 0:
                raise Exception("Input file is empty")
        else:
            raise Exception("Input file not found")

        # Resolve ffmpeg path
        ffmpeg_exe = shutil.which("ffmpeg")
        if not ffmpeg_exe:
            raise Exception("FFmpeg executable not found in PATH")

        # -vf "scale='min(1280,iw)':-2": Resize to max 720p width, keep aspect ratio
        # -crf 26: Reasonable quality/size trade-off for mobile
        # -preset veryfast: Faster encoding
        transcode_cmd = [
            ffmpeg_exe, "-y",
            "-i", input_path,
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
            "-vf", "scale='min(1280,iw)':-2",
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            temp_output_path
        ]
        
        logger.info(f"   Command: {' '.join(transcode_cmd)}")

        # Use asyncio.to_thread instead of create_subprocess_exec to avoid NotImplementedError on Windows
        # and to keep it non-blocking
        process_result = await asyncio.to_thread(
            subprocess.run,
            transcode_cmd,
            capture_output=True
        )

        logger.info(f"   FFmpeg return code: {process_result.returncode}")
        
        if process_result.returncode != 0:
            error_output = process_result.stderr.decode(errors='replace')
            logger.error(f"FFmpeg Error Output: {error_output}")
            raise Exception(f"Transcoding failed with code {process_result.returncode}")
        # 4. Move to Cache
        if os.path.exists(temp_output_path):
            shutil.move(temp_output_path, final_output_path)
            logger.info(f"✅ Encoded file saved to {final_output_path}")
        else:
            raise Exception("Output file not found after transcoding")

        # 5. Update DB
        metadata["is_encoded"] = True
        metadata["encoded_path"] = str(final_output_path)
        metadata["last_played"] = datetime.now().isoformat()
        
        await db_client.table("videos").update({"metadata": metadata}).eq("id", video_id).execute()

        # 6. Notify User
        if user_id:
            try:
                request = HTTPXRequest(connection_pool_size=1, connect_timeout=10, read_timeout=10)
                bot = Bot(token=bot_token, request=request)
                
                stream_url = f"{base_url}/watch/{short_id}"
                
                await bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"✅ **모바일 최적화 완료!**\n\n"
                        f"📹 **{title}**\n"
                        f"이제 모바일에서도 끊김 없이 재생됩니다.\n\n"
                        f"🔗 [지금 재생하기]({stream_url})"
                    ),
                    parse_mode=ParseMode.MARKDOWN
                )
                logger.info(f"🔔 Notification sent to user {user_id}")
            except Exception as notify_e:
                logger.error(f"Failed to send notification: {notify_e}")

    except Exception as e:
        logger.error(f"❌ Transcoding task failed: {repr(e)}")
        # Clean up partial files if any? (Optional)
    finally:
        # Cleanup temp dir
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info("🧹 Temp directory cleaned up")

async def cleanup_old_encoded_files(db_client):
    """Delete encoded files not played for 7 days."""
    logger.info("🧹 Running cleanup for old encoded files...")
    try:
        expiry = datetime.now() - timedelta(days=7)
        
        # This part requires fetching rows and filtering in python 
        # because metadata is JSONB and filtering inside JSONB might be complex depending on DB setup
        resp = await db_client.table("videos").select("id, metadata").not_.is_("metadata", "null").execute()
        
        count = 0
        for row in resp.data:
            metadata = row.get("metadata") or {}
            if metadata.get("is_encoded") and metadata.get("encoded_path"):
                last_played_str = metadata.get("last_played")
                if last_played_str:
                    last_played = datetime.fromisoformat(last_played_str)
                    if last_played < expiry:
                        # Expired
                        file_path = metadata["encoded_path"]
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            logger.info(f"🗑️ Removed expired file: {file_path}")
                        
                        # Update DB
                        del metadata["encoded_path"]
                        metadata["is_encoded"] = False
                        await db_client.table("videos").update({"metadata": metadata}).eq("id", row["id"]).execute()
                        count += 1
        
        logger.info(f"✅ Cleanup finished. Removed {count} files.")
        
    except Exception as e:
        logger.error(f"Cleanup failed: {e}")