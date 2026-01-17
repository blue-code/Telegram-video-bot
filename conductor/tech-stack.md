# 기술 스택: Telegram Video Bot (TVB)

## 1. 언어 및 핵심 프레임워크
- **언어:** Python 3.12+
- **봇 프레임워크:** `python-telegram-bot` (비동기 지원, 풍부한 기능)
- **웹 대시보드:** FastAPI (Backend API) + Jinja2 (Templates)

## 2. 미디어 처리 및 데이터베이스
- **다운로드 엔진:** `yt-dlp`
- **비디오/오디오 처리:** `ffmpeg`
- **데이터베이스:** Supabase (PostgreSQL) - `supabase-py` (Async)
- **eBook 처리:** `epub.js` (Frontend Viewer), `zipfile`/`xml` (Metadata Parsing)
- **코믹스 처리:** `Pillow` (Image Processing), `zipfile` (Archive Handling)
- **TTS (음성 합성):** `edge-tts` (Microsoft Edge Online TTS)

## 3. 비동기 처리 및 작업 관리
- **작업 큐:** Python `asyncio` BackgroundTasks
- **파일 I/O:** `aiofiles` (Non-blocking File Operations)
- **HTTP 클라이언트:** `httpx` (Async)

## 4. 인프라 및 배포
- **개발 및 운영 환경:** Windows / macOS / Linux
- **저장소:** Telegram Channel (Bin Channel) as Unlimited Cloud Storage