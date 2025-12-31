import os
import logging
from src.bot import main

def verify():
    print("Phase 3 Verification: Bot Interaction")
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token or token == "placeholder_token":
        print("ERROR: TELEGRAM_BOT_TOKEN is not set correctly in .env!")
        print("Please set your real bot token to verify.")
        return

    print("Starting the bot for manual verification...")
    print("Please perform the following steps in your Telegram client:")
    print("1. Send /start and verify the energetic welcome message.")
    print("2. Send /help and verify the instructions.")
    print("3. Send a YouTube URL (e.g., https://www.youtube.com/watch?v=dQw4w9WgXcQ)")
    print("4. Verify the analysis message and the appearance of quality selection buttons.")
    print("5. Click a button and verify the 'Starting work' message.")
    print("\nPress Ctrl+C to stop the bot after verification.")
    
    try:
        main()
    except KeyboardInterrupt:
        print("\nVerification stopped by user.")

if __name__ == "__main__":
    verify()
