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
from src.db import (
    get_video_by_url, save_video_metadata, get_database,
    get_user_videos, search_user_videos, get_recent_videos,
    add_favorite, remove_favorite, is_favorite, get_user_favorites,
    get_popular_videos, increment_view_count, get_video_by_id
)
from src.splitter import split_video
from src.user_manager import get_or_create_user, check_quota, increment_download_count, set_user_tier, get_user_stats
from src.link_shortener import get_or_create_short_link

load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Telegram Bot API limit for regular bots is 50MB.
# We set it to 30MB to accommodate VBR spikes and keyframe alignment issues.
MAX_FILE_SIZE = 30 * 1024 * 1024 # 30MB (Safety buffer for 50MB limit)

# Get BASE_URL from environment
BASE_URL = os.getenv("BASE_URL", "http://localhost:8000")
ADMIN_USER_ID = int(os.getenv("ADMIN_USER_ID", "0"))

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Log uncaught exceptions from the Telegram polling loop."""
    logging.error("Unhandled exception in bot: %r", context.error, exc_info=context.error)

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
        "**다운로드 명령어:**\n"
        "영상 URL을 보내주세요 - 유튜브/영상 다운로드\n\n"
        "**라이브러리 관리:**\n"
        "/library 또는 /list - 내 영상 목록 보기\n"
        "/search <키워드> - 영상 검색\n"
        "/recent - 최근 다운로드한 영상 (5개)\n"
        "/favorites - 즐겨찾기 목록\n\n"
        "**정보 & 통계:**\n"
        "/stats - 내 통계 보기\n"
        "/quota - 남은 다운로드 횟수\n"
        "/popular - 인기 영상 TOP 10\n\n"
        "**기본 명령어:**\n"
        "/start - 봇 시작하기\n"
        "/help - 이 도움말 보기\n\n"
        "즐거운 시간 되세요! 🎸"
    )
    await update.effective_message.reply_text(help_text, parse_mode='Markdown')

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming text messages to detect URLs."""
    text = update.effective_message.text
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    # Improved regex to capture full URL including path and parameters
    url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+(?:/[-\w._?%&=#/]*)?'
    urls = re.findall(url_pattern, text)
    
    if not urls:
        await update.effective_message.reply_text("음... 영상 링크가 보이지 않아요! 다시 확인해 주시겠어요? 🤔")
        return

    url = urls[0]
    
    # Check quota before processing
    try:
        has_quota, user = await check_quota(await get_database(), user_id, username)
        if not has_quota:
            remaining_time = "내일"  # You could calculate exact time here
            await update.effective_message.reply_text(
                f"⚠️ **다운로드 할당량 초과**\n\n"
                f"오늘의 다운로드 할당량({user['daily_quota']}회)을 모두 사용했습니다.\n"
                f"{remaining_time} 다시 시도해주세요!\n\n"
                f"💡 /quota 명령어로 할당량을 확인할 수 있습니다."
            )
            return
    except Exception as e:
        logging.error(f"Error checking quota: {e}")
        # Continue even if quota check fails
    
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
                        # Use BASE_URL instead of hardcoded localhost
                        db_client = await get_database()
                        short_id = await get_or_create_short_link(db_client, part['file_id'], existing_video.get('id'), user_id)
                        stream_markup = InlineKeyboardMarkup([[
                            InlineKeyboardButton("🎬 스트리밍으로 보기", url=f"{BASE_URL}/watch/{short_id}")
                        ]])
                        await update.effective_message.reply_video(
                            video=part['file_id'],
                            caption=f"다시 보기: {existing_video.get('title', '영상')}",
                            reply_markup=stream_markup
                        )
            else:
                # Legacy single file support
                await update.effective_message.reply_text(
                    f"앗! 이 영상은 이미 제가 기억하고 있어요! 🧠\n바로 보내드릴게요! (준비 중...)"
                )
                
                # Create Streaming Button with short link
                db_client = await get_database()
                short_id = await get_or_create_short_link(db_client, existing_video['file_id'], existing_video.get('id'), user_id)
                stream_markup = InlineKeyboardMarkup([[
                    InlineKeyboardButton("🎬 스트리밍으로 보기", url=f"{BASE_URL}/watch/{short_id}")
                ]])
                
                await update.effective_message.reply_video(
                    video=existing_video['file_id'],
                    caption=f"다시 보기: {existing_video.get('title', '영상')}",
                    reply_markup=stream_markup
                )
            return
        except Exception as e:
            logging.error(f"Cached send failed: {e}")
            # If cached send fails, continue to re-download

    status_message = await update.effective_message.reply_text("영상을 분석 중입니다... 잠시만 기다려 주세요! 🕵️‍♂️")
    
    try:
        info = await extract_video_info(url)
        
        # Check if it's a playlist
        if info.get('is_playlist'):
            # Handle playlist
            playlist_id = info['id']
            playlist_title = info['title']
            video_count = info['count']
            entries = info['entries']
            
            # Store playlist info in user_data
            context.user_data[f"playlist_{playlist_id}"] = {
                'title': playlist_title,
                'entries': entries,
                'url': url
            }
            
            # Create buttons for playlist actions
            buttons = [
                [InlineKeyboardButton(f"📥 전체 다운로드 ({video_count}개)", callback_data=f"pl_all|{playlist_id}|best|720")],
                [InlineKeyboardButton("🎵 전체 MP3 다운로드", callback_data=f"pl_all|{playlist_id}|bestaudio|mp3")],
            ]
            
            # Show first 5 videos as individual options
            for i, entry in enumerate(entries[:5]):
                buttons.append([InlineKeyboardButton(
                    f"▶️ {i+1}. {entry['title'][:30]}...",
                    callback_data=f"pl_single|{playlist_id}|{i}|best"
                )])
            
            if video_count > 5:
                buttons.append([InlineKeyboardButton(f"... 외 {video_count - 5}개 더보기", callback_data=f"pl_more|{playlist_id}")])
            
            reply_markup = InlineKeyboardMarkup(buttons)
            
            await status_message.edit_text(
                f"🎬 **플레이리스트 감지됨!**\n\n"
                f"**{playlist_title}**\n"
                f"총 **{video_count}**개의 영상이 있습니다.\n\n"
                f"아래에서 원하는 옵션을 선택해 주세요!",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return
        
        # Single video handling (existing logic)
        # Filter formats to show useful options (e.g., mp4 with height)
        seen_heights = set()
        buttons = []
        
        for f in info.get('formats', []):
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
            'thumbnail': info.get('thumbnail')
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
    
    # Handle stream button
    if data[0] == 'stream':
        video_id = int(data[1])
        try:
            video = await get_video_by_id(video_id)
            if video:
                file_id = video.get('file_id')
                # Get or create short link
                db_client = await get_database()
                short_id = await get_or_create_short_link(db_client, file_id, video_id, query.from_user.id)
                stream_url = f"{BASE_URL}/watch/{short_id}"
                
                # Increment view count
                await increment_view_count(video_id)
                
                await query.answer(f"스트리밍 링크: {stream_url}", show_alert=True)
        except Exception as e:
            logging.error(f"Error in stream callback: {e}")
            await query.answer("스트리밍 링크 생성 실패", show_alert=True)
        return
    
    # Handle favorite button
    elif data[0] == 'fav':
        video_id = int(data[1])
        user_id = query.from_user.id
        try:
            success = await add_favorite(user_id, video_id)
            if success:
                await query.answer("⭐ 즐겨찾기에 추가되었습니다!", show_alert=False)
            else:
                await query.answer("이미 즐겨찾기에 추가되어 있습니다.", show_alert=False)
        except Exception as e:
            logging.error(f"Error in favorite callback: {e}")
            await query.answer("즐겨찾기 추가 실패", show_alert=True)
        return
    
    # Handle unfavorite button
    elif data[0] == 'unfav':
        video_id = int(data[1])
        user_id = query.from_user.id
        try:
            success = await remove_favorite(user_id, video_id)
            if success:
                await query.answer("❌ 즐겨찾기에서 제거되었습니다!", show_alert=False)
                # Refresh favorites list
                await favorites_command(update, context)
            else:
                await query.answer("제거 실패", show_alert=True)
        except Exception as e:
            logging.error(f"Error in unfavorite callback: {e}")
            await query.answer("제거 실패", show_alert=True)
        return
    
    # Handle library pagination
    elif data[0] == 'lib_prev':
        current_page = int(data[1])
        context.user_data['library_page'] = current_page - 1
        await library_command(update, context)
        return
    
    elif data[0] == 'lib_next':
        current_page = int(data[1])
        context.user_data['library_page'] = current_page + 1
        await library_command(update, context)
        return
    
    # Handle Playlist - Download All
    if data[0] == 'pl_all':
        playlist_id = data[1]
        format_id = data[2]
        quality = data[3]
        
        playlist_data = context.user_data.get(f"playlist_{playlist_id}")
        if not playlist_data:
            await query.edit_message_text("죄송합니다. 세션이 만료되었습니다. 링크를 다시 보내주세요! 🔄")
            return
        
        entries = playlist_data['entries']
        playlist_title = playlist_data['title']
        total = len(entries)
        
        status_message = await query.edit_message_text(
            f"🎬 **{playlist_title}**\n\n"
            f"총 {total}개의 영상을 순차적으로 다운로드합니다...\n"
            f"잠시만 기다려 주세요! ⏳",
            parse_mode='Markdown'
        )
        
        success_count = 0
        fail_count = 0
        
        for i, entry in enumerate(entries):
            try:
                await status_message.edit_text(
                    f"🎬 **{playlist_title}**\n\n"
                    f"진행 중: [{i+1}/{total}] {entry['title'][:30]}...\n"
                    f"✅ 성공: {success_count} | ❌ 실패: {fail_count}",
                    parse_mode='Markdown'
                )
                
                video_url = entry['url']
                if not video_url:
                    video_url = f"https://www.youtube.com/watch?v={entry['id']}"
                
                # Store video meta for download
                context.user_data[entry['id']] = {
                    'url': video_url,
                    'title': entry['title'],
                    'duration': entry.get('duration'),
                    'thumbnail': None
                }
                
                # Download and upload (reuse existing logic)
                os.makedirs("downloads", exist_ok=True)
                file_path = await download_video(video_url, format_id, "downloads")
                
                if os.path.exists(file_path):
                    parts = await split_video(file_path, MAX_FILE_SIZE)
                    
                    for part in parts:
                        with open(part, 'rb') as video_file:
                            # Upload to Bin Channel first if configured
                            bin_channel_id = os.getenv("BIN_CHANNEL_ID")
                            file_to_send = video_file
                            actual_file_id = None
                            
                            if bin_channel_id:
                                try:
                                    video_file.seek(0)
                                    if part.lower().endswith('.mp4'):
                                        bin_msg = await context.bot.send_video(
                                            chat_id=int(bin_channel_id),
                                            video=video_file,
                                            caption=f"{entry['title']}\n\nPlaylist: {playlist_title}",
                                            supports_streaming=True,
                                            read_timeout=600, write_timeout=600, connect_timeout=60
                                        )
                                        file_to_send = bin_msg.video.file_id
                                        actual_file_id = bin_msg.video.file_id
                                    else:
                                        bin_msg = await context.bot.send_audio(
                                            chat_id=int(bin_channel_id),
                                            audio=video_file,
                                            caption=f"{entry['title']}\n\nPlaylist: {playlist_title}",
                                            read_timeout=600, write_timeout=600, connect_timeout=60
                                        )
                                        file_to_send = bin_msg.audio.file_id
                                        actual_file_id = bin_msg.audio.file_id
                                except Exception as e:
                                    logging.error(f"Bin channel upload failed: {e}")
                                    video_file.seek(0)
                            
                            # Send to user
                            if part.lower().endswith('.mp4'):
                                sent_msg = await context.bot.send_video(
                                    chat_id=query.message.chat_id,
                                    video=file_to_send,
                                    caption=f"[{i+1}/{total}] {entry['title']}",
                                    supports_streaming=True
                                )
                                if not actual_file_id:
                                    actual_file_id = sent_msg.video.file_id
                                
                                # Create short link and edit message to add streaming button
                                try:
                                    db_client = await get_database()
                                    short_id = await get_or_create_short_link(db_client, actual_file_id, None, query.from_user.id)
                                    stream_markup = InlineKeyboardMarkup([[
                                        InlineKeyboardButton("🎬 스트리밍", url=f"{BASE_URL}/watch/{short_id}")
                                    ]])
                                    await sent_msg.edit_reply_markup(reply_markup=stream_markup)
                                except Exception as e:
                                    logging.error(f"Error creating short link: {e}")
                            else:
                                await context.bot.send_audio(
                                    chat_id=query.message.chat_id,
                                    audio=file_to_send,
                                    caption=f"[{i+1}/{total}] {entry['title']}"
                                )
                        
                        # Cleanup
                        if os.path.exists(part):
                            os.remove(part)
                    
                    if os.path.exists(file_path):
                        os.remove(file_path)
                    
                    success_count += 1
                else:
                    fail_count += 1
                    
            except Exception as e:
                logging.error(f"Playlist item download failed: {e}")
                fail_count += 1
        
        await status_message.edit_text(
            f"🎬 **{playlist_title}** 다운로드 완료!\n\n"
            f"✅ 성공: {success_count}개\n"
            f"❌ 실패: {fail_count}개",
            parse_mode='Markdown'
        )
        return
    
    # Handle Playlist - Single Video
    elif data[0] == 'pl_single':
        playlist_id = data[1]
        video_index = int(data[2])
        quality = data[3]
        
        playlist_data = context.user_data.get(f"playlist_{playlist_id}")
        if not playlist_data or video_index >= len(playlist_data['entries']):
            await query.edit_message_text("죄송합니다. 세션이 만료되었습니다. 링크를 다시 보내주세요! 🔄")
            return
        
        entry = playlist_data['entries'][video_index]
        video_url = entry['url'] or f"https://www.youtube.com/watch?v={entry['id']}"
        
        # Store as single video and trigger normal download flow
        context.user_data[entry['id']] = {
            'url': video_url,
            'title': entry['title'],
            'duration': entry.get('duration'),
            'thumbnail': None
        }
        
        # Modify callback data to trigger normal 'dl' flow
        query.data = f"dl|{entry['id']}|best|720"
        data = query.data.split('|')
        # Fall through to the 'dl' handler below
    
    if data[0] == 'dl':
        video_id = data[1]
        format_id = data[2]
        quality = data[3]
        user_id = query.from_user.id
        username = query.from_user.username
        
        video_meta = context.user_data.get(video_id)
        if not video_meta:
            await query.edit_message_text("죄송합니다. 세션이 만료되었습니다. 링크를 다시 보내주세요! 🔄")
            return

        url = video_meta['url']
        
        # Check quota before downloading
        try:
            has_quota, user = await check_quota(await get_database(), user_id, username)
            if not has_quota:
                await query.edit_message_text(
                    f"⚠️ **다운로드 할당량 초과**\n\n"
                    f"오늘의 다운로드 할당량을 모두 사용했습니다.\n"
                    f"💡 /quota 명령어로 확인하세요."
                )
                return
        except Exception as e:
            logging.error(f"Error checking quota in callback: {e}")
        
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
                                # 1. Upload to Bin Channel if configured
                                bin_channel_id = os.getenv("BIN_CHANNEL_ID")
                                file_to_send = video_file
                                bin_msg = None
                                
                                if bin_channel_id:
                                    try:
                                        # Reset file pointer before upload
                                        video_file.seek(0)
                                        bin_msg = await context.bot.send_video(
                                            chat_id=int(bin_channel_id),
                                            video=video_file,
                                            caption=f"{video_meta['title']}{part_label}\n\nID: {video_id}",
                                            supports_streaming=True,
                                            read_timeout=600, 
                                            write_timeout=600, 
                                            connect_timeout=60
                                        )
                                        # Use the file_id from Bin Channel for the user
                                        file_to_send = bin_msg.video.file_id
                                    except Exception as e:
                                        logging.error(f"Failed to upload to Bin Channel: {e}")
                                        # Fallback: Upload directly to user (file_to_send remains video_file)
                                        # Reset file pointer again just in case
                                        video_file.seek(0)

                                # 2. Send to User
                                sent_msg = await context.bot.send_video(
                                    chat_id=query.message.chat_id,
                                    video=file_to_send,
                                    caption=f"{video_meta['title']}{part_label}",
                                    supports_streaming=True,
                                    read_timeout=600, 
                                    write_timeout=600, 
                                    connect_timeout=60
                                )
                                file_id = bin_msg.video.file_id if bin_msg else sent_msg.video.file_id
                                
                                # Create short link and add streaming button
                                try:
                                    db_client = await get_database()
                                    short_id = await get_or_create_short_link(db_client, file_id, None, user_id)
                                    stream_markup = InlineKeyboardMarkup([[
                                        InlineKeyboardButton("🎬 스트리밍", url=f"{BASE_URL}/watch/{short_id}")
                                    ]])
                                    await sent_msg.edit_reply_markup(reply_markup=stream_markup)
                                except Exception as e:
                                    logging.error(f"Error creating short link: {e}")
                            else:
                                # Audio logic (similar pattern)
                                bin_channel_id = os.getenv("BIN_CHANNEL_ID")
                                file_to_send = video_file
                                bin_msg = None
                                
                                if bin_channel_id:
                                    try:
                                        # Reset file pointer before upload
                                        video_file.seek(0)
                                        bin_msg = await context.bot.send_audio(
                                            chat_id=int(bin_channel_id),
                                            audio=video_file,
                                            caption=f"{video_meta['title']}{part_label}\n\nID: {video_id}",
                                            read_timeout=600,
                                            write_timeout=600,
                                            connect_timeout=60
                                        )
                                        file_to_send = bin_msg.audio.file_id
                                    except Exception as e:
                                        logging.error(f"Failed to upload audio to Bin Channel: {e}")
                                        # Reset file pointer again just in case
                                        video_file.seek(0)

                                sent_msg = await context.bot.send_audio(
                                    chat_id=query.message.chat_id,
                                    audio=file_to_send,
                                    caption=f"{video_meta['title']}{part_label}",
                                    read_timeout=600,
                                    write_timeout=600,
                                    connect_timeout=60
                                )
                                file_id = bin_msg.audio.file_id if bin_msg else sent_msg.audio.file_id
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
                            "user_id": user_id,  # Add user_id for multi-user support
                            "metadata": {
                                "quality": quality, 
                                "format_id": format_id,
                                "parts": uploaded_file_ids
                            }
                        }
                        result = await save_video_metadata(db_data)
                        logging.info("Metadata saved to database with all parts.")
                        
                        # Increment download count
                        try:
                            await increment_download_count(await get_database(), user_id)
                        except Exception as e:
                            logging.error(f"Error incrementing download count: {e}")

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


async def library_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /library or /list command."""
    user_id = update.effective_user.id
    page = int(context.args[0]) if context.args and context.args[0].isdigit() else 0
    
    # Store page in user data for pagination
    if 'library_page' not in context.user_data:
        context.user_data['library_page'] = 0
    
    page = context.user_data.get('library_page', 0)
    videos_per_page = 10
    offset = page * videos_per_page
    
    try:
        videos = await get_user_videos(user_id, limit=videos_per_page + 1, offset=offset)
        
        if not videos:
            await update.effective_message.reply_text(
                "아직 다운로드한 영상이 없어요! 🎬\n"
                "영상 URL을 보내주시면 다운로드해드릴게요!"
            )
            return
        
        has_more = len(videos) > videos_per_page
        videos = videos[:videos_per_page]
        
        # Build message
        message = f"📚 **내 영상 라이브러리** (페이지 {page + 1})\n\n"
        
        buttons = []
        for i, video in enumerate(videos):
            title = video.get('title', '제목 없음')[:40]
            duration = video.get('duration', 0)
            views = video.get('views', 0)
            
            # Format duration
            duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "N/A"
            
            message += f"{i+1}. **{title}**\n"
            message += f"   ⏱ {duration_str} | 👁 {views}회\n\n"
            
            # Add buttons for each video
            video_id = video.get('id')
            file_id = video.get('file_id')
            
            buttons.append([
                InlineKeyboardButton("🎬 스트리밍", callback_data=f"stream|{video_id}"),
                InlineKeyboardButton("⭐ 즐겨찾기", callback_data=f"fav|{video_id}")
            ])
        
        # Navigation buttons
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton("◀️ 이전", callback_data=f"lib_prev|{page}"))
        if has_more:
            nav_buttons.append(InlineKeyboardButton("다음 ▶️", callback_data=f"lib_next|{page}"))
        
        if nav_buttons:
            buttons.append(nav_buttons)
        
        reply_markup = InlineKeyboardMarkup(buttons)
        await update.effective_message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logging.error(f"Error in library_command: {e}")
        await update.effective_message.reply_text("라이브러리를 불러오는 중 오류가 발생했습니다. 😭")


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /search command."""
    user_id = update.effective_user.id
    
    if not context.args:
        await update.effective_message.reply_text(
            "검색어를 입력해주세요!\n"
            "예: /search 뮤직비디오"
        )
        return
    
    keyword = ' '.join(context.args)
    
    try:
        videos = await search_user_videos(user_id, keyword, limit=10)
        
        if not videos:
            await update.effective_message.reply_text(
                f"'{keyword}'에 대한 검색 결과가 없습니다. 🔍"
            )
            return
        
        message = f"🔍 **검색 결과: '{keyword}'**\n\n"
        
        buttons = []
        for i, video in enumerate(videos):
            title = video.get('title', '제목 없음')[:40]
            duration = video.get('duration', 0)
            duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "N/A"
            
            message += f"{i+1}. **{title}** (⏱ {duration_str})\n"
            
            video_id = video.get('id')
            buttons.append([
                InlineKeyboardButton("🎬 스트리밍", callback_data=f"stream|{video_id}"),
                InlineKeyboardButton("⭐ 즐겨찾기", callback_data=f"fav|{video_id}")
            ])
        
        reply_markup = InlineKeyboardMarkup(buttons)
        await update.effective_message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logging.error(f"Error in search_command: {e}")
        await update.effective_message.reply_text("검색 중 오류가 발생했습니다. 😭")


async def recent_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /recent command."""
    user_id = update.effective_user.id
    
    try:
        videos = await get_recent_videos(user_id, limit=5)
        
        if not videos:
            await update.effective_message.reply_text(
                "아직 다운로드한 영상이 없어요! 🎬"
            )
            return
        
        message = "⏰ **최근 다운로드한 영상 (5개)**\n\n"
        
        buttons = []
        for i, video in enumerate(videos):
            title = video.get('title', '제목 없음')[:40]
            duration = video.get('duration', 0)
            duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "N/A"
            
            message += f"{i+1}. **{title}** (⏱ {duration_str})\n"
            
            video_id = video.get('id')
            buttons.append([
                InlineKeyboardButton("🎬 스트리밍", callback_data=f"stream|{video_id}"),
                InlineKeyboardButton("⭐ 즐겨찾기", callback_data=f"fav|{video_id}")
            ])
        
        reply_markup = InlineKeyboardMarkup(buttons)
        await update.effective_message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logging.error(f"Error in recent_command: {e}")
        await update.effective_message.reply_text("최근 영상을 불러오는 중 오류가 발생했습니다. 😭")


async def favorites_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /favorites command."""
    user_id = update.effective_user.id
    page = 0
    videos_per_page = 10
    offset = page * videos_per_page
    
    try:
        videos = await get_user_favorites(user_id, limit=videos_per_page + 1, offset=offset)
        
        if not videos:
            await update.effective_message.reply_text(
                "즐겨찾기한 영상이 없어요! ⭐\n"
                "영상 메시지에서 '⭐ 즐겨찾기' 버튼을 눌러 추가하세요!"
            )
            return
        
        has_more = len(videos) > videos_per_page
        videos = videos[:videos_per_page]
        
        message = "⭐ **즐겨찾기 목록**\n\n"
        
        buttons = []
        for i, video in enumerate(videos):
            title = video.get('title', '제목 없음')[:40]
            duration = video.get('duration', 0)
            duration_str = f"{duration // 60}:{duration % 60:02d}" if duration else "N/A"
            
            message += f"{i+1}. **{title}** (⏱ {duration_str})\n"
            
            video_id = video.get('id')
            buttons.append([
                InlineKeyboardButton("🎬 스트리밍", callback_data=f"stream|{video_id}"),
                InlineKeyboardButton("❌ 제거", callback_data=f"unfav|{video_id}")
            ])
        
        reply_markup = InlineKeyboardMarkup(buttons)
        await update.effective_message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logging.error(f"Error in favorites_command: {e}")
        await update.effective_message.reply_text("즐겨찾기 목록을 불러오는 중 오류가 발생했습니다. 😭")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /stats command."""
    user_id = update.effective_user.id
    
    try:
        stats = await get_user_stats(await get_database(), user_id)
        
        if not stats:
            await update.effective_message.reply_text("통계를 불러올 수 없습니다. 😭")
            return
        
        user = stats['user']
        video_count = stats['video_count']
        total_storage = stats['total_storage']
        favorites_count = stats['favorites_count']
        
        # Format storage size
        storage_mb = total_storage / (1024 * 1024)
        storage_str = f"{storage_mb:.2f} MB" if storage_mb < 1024 else f"{storage_mb / 1024:.2f} GB"
        
        tier_emoji = "👑" if user['tier'] == 'premium' else "🆓"
        
        message = (
            f"📊 **내 통계**\n\n"
            f"**등급:** {tier_emoji} {user['tier'].upper()}\n"
            f"**총 다운로드:** {user['total_downloads']}회\n"
            f"**오늘 다운로드:** {user['downloads_today']}/{user['daily_quota']}회\n"
            f"**저장된 영상:** {video_count}개\n"
            f"**즐겨찾기:** {favorites_count}개\n"
            f"**총 저장 용량:** {storage_str}\n"
        )
        
        await update.effective_message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        logging.error(f"Error in stats_command: {e}")
        await update.effective_message.reply_text("통계를 불러오는 중 오류가 발생했습니다. 😭")


async def quota_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /quota command."""
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    try:
        has_quota, user = await check_quota(await get_database(), user_id, username)
        
        remaining = user['daily_quota'] - user['downloads_today']
        
        if user['tier'] == 'premium':
            message = "👑 **프리미엄 사용자**\n\n무제한 다운로드를 즐기세요! 🎉"
        else:
            message = (
                f"📊 **다운로드 할당량**\n\n"
                f"**오늘 남은 횟수:** {remaining}/{user['daily_quota']}\n"
                f"**사용한 횟수:** {user['downloads_today']}회\n\n"
            )
            
            if remaining <= 0:
                message += "⚠️ 오늘의 할당량을 모두 사용했습니다.\n내일 다시 시도해주세요!"
            elif remaining <= 3:
                message += "⚠️ 할당량이 얼마 남지 않았습니다!"
        
        await update.effective_message.reply_text(message, parse_mode='Markdown')
        
    except Exception as e:
        logging.error(f"Error in quota_command: {e}")
        await update.effective_message.reply_text("할당량을 확인하는 중 오류가 발생했습니다. 😭")


async def popular_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /popular command."""
    try:
        videos = await get_popular_videos(limit=10)
        
        if not videos:
            await update.effective_message.reply_text("아직 인기 영상이 없어요! 🎬")
            return
        
        message = "🔥 **인기 영상 TOP 10**\n\n"
        
        buttons = []
        for i, video in enumerate(videos):
            title = video.get('title', '제목 없음')[:40]
            views = video.get('views', 0)
            
            message += f"{i+1}. **{title}** (👁 {views}회)\n"
            
            video_id = video.get('id')
            buttons.append([
                InlineKeyboardButton("🎬 스트리밍", callback_data=f"stream|{video_id}")
            ])
        
        reply_markup = InlineKeyboardMarkup(buttons)
        await update.effective_message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logging.error(f"Error in popular_command: {e}")
        await update.effective_message.reply_text("인기 영상을 불러오는 중 오류가 발생했습니다. 😭")


async def grant_premium_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /grant_premium command (admin only)."""
    if update.effective_user.id != ADMIN_USER_ID:
        await update.effective_message.reply_text("⛔ 이 명령어는 관리자만 사용할 수 있습니다.")
        return
    
    if not context.args or not context.args[0].isdigit():
        await update.effective_message.reply_text(
            "사용법: /grant_premium <user_id>\n"
            "예: /grant_premium 123456789"
        )
        return
    
    target_user_id = int(context.args[0])
    
    try:
        success = await set_user_tier(await get_database(), target_user_id, 'premium')
        
        if success:
            await update.effective_message.reply_text(
                f"✅ 사용자 {target_user_id}에게 프리미엄 등급을 부여했습니다!"
            )
        else:
            await update.effective_message.reply_text("❌ 프리미엄 등급 부여에 실패했습니다.")
            
    except Exception as e:
        logging.error(f"Error in grant_premium_command: {e}")
        await update.effective_message.reply_text("오류가 발생했습니다. 😭")


async def queue_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for /queue command to show download queue status."""
    user_id = update.effective_user.id
    
    try:
        # Get queue status from queue_manager
        from src.queue_manager import get_queue_status
        
        queue_status = await get_queue_status(user_id)
        
        if not queue_status:
            await update.effective_message.reply_text(
                "📋 **다운로드 큐**\n\n"
                "현재 대기 중인 다운로드가 없습니다.\n"
                "영상 URL을 보내서 다운로드를 시작하세요!",
                parse_mode='Markdown'
            )
            return
        
        current_download = queue_status.get('current')
        queued_items = queue_status.get('queue', [])
        
        message = "📋 **다운로드 큐 상태**\n\n"
        
        if current_download:
            progress = current_download.get('progress', 0)
            title = current_download.get('title', 'Unknown')
            message += f"**⬇️ 현재 다운로드 중:**\n"
            message += f"📹 {title[:40]}\n"
            message += f"진행률: {progress}%\n\n"
        
        if queued_items:
            message += f"**⏳ 대기 중 ({len(queued_items)}개):**\n"
            for i, item in enumerate(queued_items[:5]):
                title = item.get('title', 'Unknown')
                message += f"{i+1}. {title[:40]}\n"
            
            if len(queued_items) > 5:
                message += f"\n... 외 {len(queued_items) - 5}개\n"
        
        # Add control buttons
        buttons = []
        if current_download:
            buttons.append([
                InlineKeyboardButton("⏸ 일시정지", callback_data="queue_pause"),
                InlineKeyboardButton("❌ 취소", callback_data="queue_cancel")
            ])
        
        reply_markup = InlineKeyboardMarkup(buttons) if buttons else None
        
        await update.effective_message.reply_text(
            message,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logging.error(f"Error in queue_command: {e}")
        await update.effective_message.reply_text(
            "📋 **다운로드 큐**\n\n"
            "큐 상태를 확인할 수 없습니다.\n"
            "현재 구현 중인 기능입니다.",
            parse_mode='Markdown'
        )


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
    
    # Library management commands
    application.add_handler(CommandHandler("library", library_command))
    application.add_handler(CommandHandler("list", library_command))
    application.add_handler(CommandHandler("search", search_command))
    application.add_handler(CommandHandler("recent", recent_command))
    application.add_handler(CommandHandler("favorites", favorites_command))
    
    # Statistics and info commands
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("quota", quota_command))
    application.add_handler(CommandHandler("popular", popular_command))
    
    # Admin commands
    application.add_handler(CommandHandler("grant_premium", grant_premium_command))
    
    # Queue management commands
    application.add_handler(CommandHandler("queue", queue_command))
    
    # Message and callback handlers
    application.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_error_handler(error_handler)
    
    # Run the bot
    logging.info("Starting TVB Bot... 🚀")
    application.run_polling()

if __name__ == '__main__':
    main()
