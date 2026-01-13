import asyncio
import os
import logging
import tempfile
import shutil
import zipfile
import httpx
from pathlib import Path
from telegram import Bot
from telegram.request import HTTPXRequest
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

DOWNLOAD_CACHE_DIR = Path("download_cache")
DOWNLOAD_CACHE_DIR.mkdir(exist_ok=True)

async def get_telegram_file_url(bot_token, file_id):
    url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url)
        data = resp.json()
        if not data.get("ok"):
            raise Exception(f"Telegram getFile failed: {data}")
        file_path = data["result"]["file_path"]
        return f"https://api.telegram.org/file/bot{bot_token}/{file_path}"

async def download_file(client, url, dest_path):
    try:
        async with client.stream("GET", url) as r:
            r.raise_for_status()
            with open(dest_path, "wb") as f:
                async for chunk in r.aiter_bytes(chunk_size=65536):
                    f.write(chunk)
        return True
    except Exception as e:
        logger.error(f"Download failed for {url}: {e}")
        return False

async def notify_user(bot_token, user_id, message):
    try:
        request = HTTPXRequest(connection_pool_size=1, connect_timeout=10, read_timeout=10)
        bot = Bot(token=bot_token, request=request)
        await bot.send_message(chat_id=user_id, text=message, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Failed to notify user {user_id}: {e}")

async def prepare_download_task(
    task_id: str,
    files_info: list, # List of {'name': str, 'parts': [file_id, ...]}
    user_id: int,
    bot_token: str,
    base_url: str
):
    temp_dir = tempfile.mkdtemp()
    is_zip = len(files_info) > 1
    
    # Determine final filename
    if is_zip:
        final_name = f"files_{task_id[:8]}.zip"
        final_path = DOWNLOAD_CACHE_DIR / final_name
    else:
        final_name = files_info[0]['name']
        final_path = DOWNLOAD_CACHE_DIR / final_name
        # Avoid overwrite collision
        if final_path.exists():
            final_name = f"{Path(final_name).stem}_{task_id[:4]}{Path(final_name).suffix}"
            final_path = DOWNLOAD_CACHE_DIR / final_name

    try:
        logger.info(f"Task {task_id}: Preparing {len(files_info)} items for User {user_id}")
        await notify_user(bot_token, user_id, f"⏳ <b>다운로드 준비 중...</b>\n{len(files_info)}개의 파일을 처리하고 있습니다.")

        prepared_files = [] # Paths to fully assembled files in temp_dir

        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, read=600.0)) as client:
            for item in files_info:
                file_name = item['name']
                parts = item['parts']
                
                # Download all parts
                part_paths = []
                for i, fid in enumerate(parts):
                    url = await get_telegram_file_url(bot_token, fid)
                    part_name = f"{file_name}.part{i}"
                    dest = os.path.join(temp_dir, part_name)
                    if await download_file(client, url, dest):
                        part_paths.append(dest)
                    else:
                        raise Exception(f"Failed to download part of {file_name}")
                
                # Assemble parts
                assembled_path = os.path.join(temp_dir, file_name)
                with open(assembled_path, 'wb') as outfile:
                    for part in part_paths:
                        with open(part, 'rb') as infile:
                            shutil.copyfileobj(infile, outfile)
                        os.remove(part) # Clean up part
                
                prepared_files.append(assembled_path)

        # Final Package
        if is_zip:
            with zipfile.ZipFile(final_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for f in prepared_files:
                    zipf.write(f, arcname=os.path.basename(f))
        else:
            shutil.move(prepared_files[0], final_path)

        # Notify
        download_link = f"{base_url}/api/files/download_ready/{task_id}/{final_name}"
        await notify_user(
            bot_token, 
            user_id, 
            f"✅ <b>준비 완료!</b>\n\n📁 {final_name}\n\n🔗 <a href='{download_link}'>다운로드 받기</a>"
        )

    except Exception as e:
        logger.error(f"Task {task_id} failed: {e}")
        await notify_user(bot_token, user_id, f"❌ <b>실패</b>\n작업 중 오류가 발생했습니다: {e}")
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)

async def cleanup_old_downloads():
    """Delete files in download cache older than 7 days."""
    logger.info("🧹 Cleaning up old downloads...")
    try:
        now = datetime.now().timestamp()
        retention_days = 7
        retention_seconds = retention_days * 86400
        
        if not DOWNLOAD_CACHE_DIR.exists():
            return

        count = 0
        for item in DOWNLOAD_CACHE_DIR.iterdir():
            if item.is_file():
                mtime = item.stat().st_mtime
                if now - mtime > retention_seconds:
                    try:
                        item.unlink()
                        logger.info(f"Deleted expired download: {item.name}")
                        count += 1
                    except Exception as e:
                        logger.error(f"Failed to delete {item.name}: {e}")
        
        if count > 0:
            logger.info(f"✅ Cleanup complete. Removed {count} files.")
    except Exception as e:
        logger.error(f"Cleanup error: {e}")