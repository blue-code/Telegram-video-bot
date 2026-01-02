import os
import logging
import re
import asyncio
import time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram.request import HTTPXRequest
from dotenv import load_dotenv

from src.downloader import extract_video_info, download_video
from src.db import get_video_by_url, save_video_metadata
from src.splitter import split_video

load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Telegram Bot API limit for regular bots is 50MB.
# We set it to 30MB to accommodate VBR spikes and keyframe alignment issues.
MAX_FILE_SIZE = 30 * 1024 * 1024 # 30MB (Safety buffer for 50MB limit)

def get_progress_bar(percentage):
    """Generates a simple text progress bar."""
    completed = int(percentage / 10)
    return "█" * completed + "░" * (10 - completed)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /start command."""
    welcome_text = (
        "와우! 반가워요! 🚀\n"
        "저는 당신의 전용 영상 도우미 **TVB** 입니다!\n\n"
        "유튜브 링크를 보내주시면 번개같은 속도로 다운로드해서 텔레그램으로 전송해 드릴게요! ⚡️\n"
        "업로드된 영상은 제가 기억해두었다가 언제든 다시 보실 수 있답니다!\n\n"
        "시작하려면 영상 링크를 저에게 보내주세요! 궁금한 게 있다면 /help 를 입력하세요!"
    )
    await update.effective_message.reply_text(welcome_text, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /help command."""
    help_text = (
        "도움이 필요하신가요? 걱정 마세요! 🙌\n\n"
        "**사용 방법:**\n"
        "1. 유튜브나 다른 영상 사이트의 URL을 저에게 보내주세요.\n"
        "2. 제가 분석한 후에 화질을 선택하실 수 있는 메뉴를 보여드릴게요.\n"
        "3. 화질을 선택하면 다운로드와 전송이 시작됩니다! ⬇️\n\n"
        "**명령어 리스트:**\n"
        "/start - 봇 시작하기\n"
        "/help - 이 도움말 보기\n\n"
        "즐거운 시간 되세요! 🎸"
    )
    await update.effective_message.reply_text(help_text, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages to detect URLs."""
    text = update.effective_message.text
    # Improved regex to capture full URL including path and parameters
    url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+(?:/[-\w._?%&=#/]*)?'
    urls = re.findall(url_pattern, text)
    
    if not urls:
        await update.effective_message.reply_text("음... 영상 링크가 보이지 않아요! 다시 확인해 주시겠어요? 🤔")
        return

    url = urls[0]
    
    # Check if already in DB
    existing_video = await get_video_by_url(url)
    if existing_video:
        try:
            # Check for multiple parts in metadata
            parts = existing_video.get('metadata', {}).get('parts', [])
            
            if parts:
                await update.effective_message.reply_text(
                    f"앗! 이 영상은 이미 제가 기억하고 있어요! 🧠\n총 {len(parts)}개의 파트로 나누어 보내드릴게요! (준비 중...)"
                )
                for part in parts:
                    if part.get('type') == 'audio':
                        await update.effective_message.reply_audio(
                            audio=part['file_id'],
                            caption=f"다시 보기: {existing_video.get('title', '오디오')}"
                        )
                    else:
                        await update.effective_message.reply_video(
                            video=part['file_id'],
                            caption=f"다시 보기: {existing_video.get('title', '영상')}"
                        )
            else:
                # Legacy single file support
                await update.effective_message.reply_text(
                    f"앗! 이 영상은 이미 제가 기억하고 있어요! 🧠\n바로 보내드릴게요! (준비 중...)"
                )
                await update.effective_message.reply_video(
                    video=existing_video['file_id'],
                    caption=f"다시 보기: {existing_video.get('title', '영상')}"
                )
            return
        except Exception as e:
            logging.error(f"Cached send failed: {e}")
            # If cached send fails, continue to re-download

    status_message = await update.effective_message.reply_text("영상을 분석 중입니다... 잠시만 기다려 주세요! 🕵️‍♂️")
    
    try:
        info = await extract_video_info(url)
        
        # Filter formats to show useful options (e.g., mp4 with height)
        seen_heights = set()
        buttons = []
        
        for f in info['formats']:
            h = f.get('height')
            if h and h not in seen_heights and f.get('ext') == 'mp4':
                seen_heights.add(h)
                buttons.append([InlineKeyboardButton(
                    f"{h}p (MP4)", 
                    callback_data=f"dl|{info['id']}|{f['format_id']}|{h}"
                )])
        
        # Add MP3 option
        buttons.append([InlineKeyboardButton("Audio only (MP3) 🎵", callback_data=f"dl|{info['id']}|bestaudio|mp3")])
        
        reply_markup = InlineKeyboardMarkup(buttons)
        
        # Store metadata in user_data
        context.user_data[info['id']] = {
            'url': url,
            'title': info['title'],
            'duration': info['duration'],
            'thumbnail': info['thumbnail']
        }
        
        await status_message.edit_text(
            f"**{info['title']}**\n\n"
            f"영상을 찾았어요! 원하시는 화질을 선택해 주세요! ⬇️",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logging.error(f"Error extracting info: {e}")
        await status_message.edit_text(f"으악! 영상 정보를 가져오는데 실패했어요... 😭\n사유: {str(e)}")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline keyboard callbacks."""
    query = update.callback_query
    await query.answer()
    
    data = query.data.split('|')
    if data[0] == 'dl':
        video_id = data[1]
        format_id = data[2]
        quality = data[3]
        
        video_meta = context.user_data.get(video_id)
        if not video_meta:
            await query.edit_message_text("죄송합니다. 세션이 만료되었습니다. 링크를 다시 보내주세요! 🔄")
            return

        url = video_meta['url']
        status_message = await query.edit_message_text(
            f"선택하신 {quality} 화질로 작업을 시작합니다! 🚀\n"
            "먼저 영상을 다운로드할게요... 💪"
        )
        
        last_update_time = 0
        loop = asyncio.get_running_loop()
        
        def progress_hook(d):
            nonlocal last_update_time
            if d['status'] == 'downloading':
                current_time = time.time()
                if current_time - last_update_time > 3: # Update every 3s
                    p = d.get('downloaded_bytes', 0) / d.get('total_bytes', 1) * 100
                    p_str = f"{p:.1f}%"
                    speed = d.get('_speed_str', 'N/A')
                    eta = d.get('_eta_str', 'N/A')
                    bar = get_progress_bar(p)
                    
                    text = (
                        f"**영상 다운로드 중...** ⬇️\n\n"
                        f"진행률: `{bar}` {p_str}\n"
                        f"속도: {speed} | 남은 시간: {eta}"
                    )
                    
                    asyncio.run_coroutine_threadsafe(
                        status_message.edit_text(text, parse_mode='Markdown'),
                        loop
                    )
                    last_update_time = current_time

        try:
            # 1. Download
            os.makedirs("downloads", exist_ok=True)
            file_path = await download_video(
                url, 
                format_id, 
                "downloads", 
                progress_hook=progress_hook
            )
            
            logging.info(f"Downloaded file: {file_path}")
            if not os.path.exists(file_path):
                logging.error(f"File not found on disk after download: {file_path}")
                # Try to list directory for debugging
                logging.info(f"Files in downloads/: {os.listdir('downloads')}")
            
            # 2. Split if necessary
            logging.info(f"Checking if split is needed for: {file_path}")
            await status_message.edit_text("다운로드 완료! 🎉 파일을 검사하고 업로드를 준비합니다... 🔍")
            parts = await split_video(file_path, MAX_FILE_SIZE)
            logging.info(f"Split completed. Number of parts: {len(parts)}")
            
            # 3. Upload to Telegram
            uploaded_file_ids = []
            for i, part in enumerate(parts):
                part_label = f" (Part {i+1}/{len(parts)})" if len(parts) > 1 else ""
                logging.info(f"Uploading part {i+1}/{len(parts)}: {part}")
                await status_message.edit_text(f"텔레그램으로 업로드 중입니다...{part_label} 📤")
                
                with open(part, 'rb') as video_file:
                    # Send as video if it's an mp4, otherwise as document (mp3)
                    
                    # Retry logic for upload
                    max_retries = 3
                    for attempt in range(max_retries):
                        try:
                            if part.lower().endswith('.mp4'):
                                sent_msg = await context.bot.send_video(
                                    chat_id=query.message.chat_id,
                                    video=video_file,
                                    caption=f"{video_meta['title']}{part_label}",
                                    supports_streaming=True,
                                    read_timeout=600, 
                                    write_timeout=600, 
                                    connect_timeout=60
                                )
                                file_id = sent_msg.video.file_id
                            else:
                                sent_msg = await context.bot.send_audio(
                                    chat_id=query.message.chat_id,
                                    audio=video_file,
                                    caption=f"{video_meta['title']}{part_label}",
                                    read_timeout=600,
                                    write_timeout=600,
                                    connect_timeout=60
                                )
                                file_id = sent_msg.audio.file_id
                            break # Success, exit retry loop
                        except Exception as e:
                            logging.error(f"Upload failed (attempt {attempt+1}/{max_retries}): {e}")
                            if attempt == max_retries - 1:
                                raise e # Re-raise on last attempt
                            await asyncio.sleep(5) # Wait before retry
                            # Reset file pointer for retry
                            video_file.seek(0)

                    
                    # Store file_id and type for bulk update
                    uploaded_file_ids.append({
                        "file_id": file_id,
                        "type": "video" if part.lower().endswith('.mp4') else "audio"
                    })

                    # 4. Save metadata to Supabase (after last part)
                    if i == len(parts) - 1:
                        db_data = {
                            "url": url,
                            "file_id": uploaded_file_ids[0]['file_id'], # Keep primary ID compatibility
                            "title": video_meta['title'],
                            "duration": video_meta['duration'],
                            "thumbnail": video_meta['thumbnail'],
                            "metadata": {
                                "quality": quality, 
                                "format_id": format_id,
                                "parts": uploaded_file_ids
                            }
                        }
                        await save_video_metadata(db_data)
                        logging.info("Metadata saved to database with all parts.")

            logging.info("All parts uploaded successfully.")
            await status_message.delete()
            
            # Cleanup files
            for part in parts:
                if os.path.exists(part):
                    os.remove(part)
            if os.path.exists(file_path):
                os.remove(file_path)
                
        except Exception as e:
            logging.error(f"Pipeline error: {e}")
            await status_message.edit_text(f"작업 중 오류가 발생했습니다... 😭\n사유: {str(e)}")


def main():
    """Start the bot."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logging.error("TELEGRAM_BOT_TOKEN not found in environment variables!")
        return

    request = HTTPXRequest(connection_pool_size=8, read_timeout=180, write_timeout=180, connect_timeout=60)
    application = ApplicationBuilder().token(token).request(request).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Run the bot
    logging.info("Starting TVB Bot... 🚀")
    application.run_polling()

if __name__ == '__main__':
    main()