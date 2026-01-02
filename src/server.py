from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
import os
import httpx
import logging
from dotenv import load_dotenv

# Initialize
load_dotenv()
logging.basicConfig(level=logging.INFO)
app = FastAPI()
templates = Jinja2Templates(directory="templates")

# Mock DB or Bot interaction for now
async def get_file_path_from_telegram(file_id):
    """
    In a real scenario, we would need to:
    1. Get file_path from getFile API using bot token
    2. Construct download URL: https://api.telegram.org/file/bot<token>/<file_path>
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="Bot token not valid")
        
    async with httpx.AsyncClient() as client:
        # 1. Get File Path
        resp = await client.get(f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}")
        data = resp.json()
        
        if not data.get("ok"):
            raise HTTPException(status_code=404, detail="File not found on Telegram")
            
        file_path = data["result"]["file_path"]
        return f"https://api.telegram.org/file/bot{token}/{file_path}"

@app.get("/watch/{file_id}", response_class=HTMLResponse)
async def watch_video(request: Request, file_id: str):
    return templates.TemplateResponse("watch.html", {"request": request, "file_id": file_id})

@app.get("/stream/{file_id}")
async def stream_video(file_id: str):
    """Proxy stream from Telegram to Browser"""
    try:
        download_url = await get_file_path_from_telegram(file_id)
        
        # Create a generator to stream chunks
        async def iter_file():
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("GET", download_url) as r:
                    async for chunk in r.aiter_bytes():
                        yield chunk

        return StreamingResponse(iter_file(), media_type="video/mp4")
        
    except Exception as e:
        logging.error(f"Streaming error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
