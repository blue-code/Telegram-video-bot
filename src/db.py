import os
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "telegram_video_bot"
VIDEO_COLLECTION = "videos"

client = None

async def get_database():
    global client
    if client is None:
        if not MONGO_URI:
             # Fallback or error if env not set, but for now let's assume valid config
             # or let Motor handle it.
             pass
        client = AsyncIOMotorClient(MONGO_URI)
    return client[DB_NAME]

async def close_database():
    global client
    if client:
        client.close()
        client = None

async def save_video_metadata(data: dict):
    db = await get_database()
    result = await db[VIDEO_COLLECTION].insert_one(data)
    return result.inserted_id

async def get_video_by_url(url: str):
    db = await get_database()
    return await db[VIDEO_COLLECTION].find_one({"url": url})

async def get_video_by_file_id(file_id: str):
    db = await get_database()
    return await db[VIDEO_COLLECTION].find_one({"file_id": file_id})