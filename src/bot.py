import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from dotenv import load_dotenv

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
    
    # Run the bot
    logging.info("Starting TVB Bot... 🚀")
    application.run_polling()

if __name__ == '__main__':
    main()
