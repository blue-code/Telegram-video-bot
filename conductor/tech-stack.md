# 기술 스택: Telegram Video Bot (TVB)

## 1. 언어 및 핵심 프레임워크
- **언어:** Python 3.10+
- **봇 프레임워크:** `python-telegram-bot` (비동기 지원, 풍부한 기능)
- **웹 대시보드:** FastAPI (Backend API) + Jinja2 (Templates)

## 2. 영상 처리 및 데이터베이스
- **다운로드 엔진:** `yt-dlp`
- **미디어 처리:** `ffmpeg`
- **데이터베이스:** MongoDB Atlas (Driver: `motor`)

## 3. 비동기 처리 및 작업 관리
- **작업 큐:** Python `asyncio` Task

## 4. 인프라 및 배포 (초기 단계)
- **개발 및 운영 환경:** macOS (Local)
- **향후 계획:** Docker 컨테이너화 및 클라우드 배포 고려.
