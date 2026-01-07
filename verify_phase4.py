import os
import logging
from src.bot import main

def verify():
    print("Phase 4 Verification: Full Pipeline (Download & Upload)")
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN is not set!")
        return

    print("Starting the bot for pipeline verification...")
    print("Please perform the following steps in your Telegram client:")
    print("1. Send a YouTube URL.")
    print("2. Select a quality (start with a small one like 360p for speed).")
    print("3. Verify the real-time progress bar updates.")
    print("4. Verify that the video is uploaded to the chat after download.")
    print("5. Send the SAME URL again and verify it is resent INSTANTLY from cache.")
    print("\nPress Ctrl+C to stop the bot after verification.")
    
    try:
        main()
    except KeyboardInterrupt:
        print("\nVerification stopped by user.")

if __name__ == "__main__":
    verify()