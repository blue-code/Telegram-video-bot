import asyncio
import os
import logging
import ssl
import certifi
import pymongo.ssl_support
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO)

# Monkeypatch pymongo to allow legacy ciphers
original_get_ssl_context = pymongo.ssl_support.get_ssl_context

def patched_get_ssl_context(*args, **kwargs):
    ctx = original_get_ssl_context(*args, **kwargs)
    try:
        # Lower security level to allow legacy ciphers
        ctx.set_ciphers('DEFAULT:@SECLEVEL=0')
        print("DEBUG: Successfully set legacy ciphers on SSLContext")
    except Exception as e:
        print(f"DEBUG: Failed to set ciphers: {e}")
    return ctx

pymongo.ssl_support.get_ssl_context = patched_get_ssl_context

MONGO_URI = os.getenv("MONGO_URI")
VIDEO_COLLECTION = "videos"

async def test_db():
    print("Testing DB connection with patched pymongo...")
    
    try:
        # We must NOT pass tlsContext if we want pymongo to use its own get_ssl_context
        # We just pass tlsCAFile
        client = AsyncIOMotorClient(MONGO_URI, tls=True, tlsCAFile=certifi.where())
        
        db = client["telegram_video_bot"]
        
        # Try query
        print("Attempting query...")
        result = await db[VIDEO_COLLECTION].find_one({"url": "http://test.com/nonexistent"}, serverSelectionTimeoutMS=5000)
        print(f"Query result: {result}")
        print("SUCCESS! DB Connection works.")
        
    except Exception as e:
        print(f"CAUGHT EXCEPTION: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(test_db())
