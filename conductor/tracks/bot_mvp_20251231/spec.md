# Spec: Telegram Bot MVP (bot_mvp_20251231)

## 1. 개요
유튜브 및 다양한 영상 소스에서 영상을 추출하여 텔레그램으로 전송하고, 몽고디비 아틀라스에 기록을 남겨 추후 재시청이 가능하게 하는 봇의 최소 기능 제품(MVP) 사양입니다.

## 2. 핵심 아키텍처
- **Language:** Python 3.10+ (Asyncio)
- **Framework:** `python-telegram-bot`
- **Database:** MongoDB Atlas (Driver: `motor`)
- **Tools:** `yt-dlp` (Downloading), `FFmpeg` (Processing & Splitting)
- **Queue:** Python 내장 `asyncio.Queue` (단일 세션 로컬 처리 최적화)

## 3. 주요 기능 상세
### 3.1 URL 처리 및 분석
- 사용자가 URL 전송 시 `yt-dlp`를 사용하여 영상 정보(제목, 화질 목록, 썸네일) 추출.
- 인라인 버튼을 통해 화질(720p, 1080p 등) 및 형식(MP4, MP3) 선택 제공.

### 3.2 영상 다운로드 및 처리
- 선택된 옵션으로 로컬 임시 폴더에 다운로드.
- **실시간 피드백:** 텔레그램 메시지를 통해 다운로드 진행률(%) 표시.
- **자동 분할:** 영상이 2GB를 초과할 경우 FFmpeg를 사용하여 2GB 단위로 자동 분할.

### 3.3 텔레그램 업로드 및 저장
- 처리된 영상/오디오 파일을 텔레그램으로 전송.
- 전송 후 생성된 `file_id`를 몽고디비에 저장 (중복 전송 방지 및 스트리밍용).

### 3.4 데이터베이스 스키마 (MongoDB)
- **Videos Collection:**
  - `url` (String, Index)
  - `title` (String)
  - `file_id` (String)
  - `quality` (String)
  - `size` (Number)
  - `duration` (Number)
  - `user_id` (Number)
  - `created_at` (Date)

## 4. UI/UX 가이드라인
- **페르소나:** 활기차고 친절한 친구 말투 (이모지 활용).
- **진행 표시:** 텍스트 기반 진행률 바 (`[████░░░░░░] 40%`).
- **에러 메시지:** 기술적 원인을 포함한 상세 안내.
