import os
import logging
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from dotenv import load_dotenv

from src.downloader import extract_video_info
from src.db import get_video_by_url

load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

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
    url_pattern = r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+'
    urls = re.findall(url_pattern, text)
    
    if not urls:
        await update.effective_message.reply_text("음... 영상 링크가 보이지 않아요! 다시 확인해 주시겠어요? 🤔")
        return

    url = urls[0]
    
    # Check if already in DB
    existing_video = await get_video_by_url(url)
    if existing_video:
        await update.effective_message.reply_text(
            f"앗! 이 영상은 이미 제가 기억하고 있어요! 🧠\n바로 보내드릴게요! (준비 중...)"
        )
        # TODO: Implement Phase 5 immediate resend
        return

    status_message = await update.effective_message.reply_text("영상을 분석 중입니다... 잠시만 기다려 주세요! 🕵️‍♂️")
    
    try:
        info = await extract_video_info(url)
        
        # Filter formats to show useful options (e.g., mp4 with height)
        # Simple heuristic: unique heights
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
        
        await query.edit_message_text(
            f"선택하신 {quality} 화질로 작업을 시작합니다! 🚀\n"
            "조금만 기다려 주세요... 제가 열심히 일하고 있어요! 💪"
        )
        # TODO: Implement Phase 4 pipeline

def main():
    """Start the bot."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        logging.error("TELEGRAM_BOT_TOKEN not found in environment variables!")
        return

    application = ApplicationBuilder().token(token).build()
    
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