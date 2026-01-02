import os
from supabase import create_async_client, AsyncClient
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
VIDEO_TABLE = "videos"

client: AsyncClient = None

async def get_database() -> AsyncClient:
    """Returns the Supabase async client instance."""
    global client
    if client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("SUPABASE_URL or SUPABASE_KEY not found in environment variables!")
        client = await create_async_client(SUPABASE_URL, SUPABASE_KEY)
    return client

async def close_database():
    """No explicit close needed for Supabase client, but kept for interface compatibility."""
    global client
    client = None

async def save_video_metadata(data: dict):
    """
    Saves video metadata to Supabase.
    If the URL already exists, it will be updated (upsert).
    """
    sb = await get_database()
    result = await sb.table(VIDEO_TABLE).upsert(data, on_conflict="url").execute()
    return result.data

async def get_video_by_url(url: str):
    """Retrieves video metadata by original URL."""
    sb = await get_database()
    result = await sb.table(VIDEO_TABLE).select("*").eq("url", url).execute()
    return result.data[0] if result.data else None

async def get_video_by_file_id(file_id: str):
    """Retrieves video metadata by Telegram File ID."""
    sb = await get_database()
    result = await sb.table(VIDEO_TABLE).select("*").eq("file_id", file_id).execute()
    return result.data[0] if result.data else None
