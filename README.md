# 🎬 TVB (Telegram Video Bot)

> 유튜브 영상을 텔레그램으로 다운로드하고, 웹에서 스트리밍하고, 플레이리스트까지 한 번에!

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![Telegram Bot API](https://img.shields.io/badge/Telegram%20Bot%20API-7.0-blue.svg)](https://core.telegram.org/bots/api)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## 📖 목차

- [✨ 주요 기능](#-주요-기능)
- [🏗️ 아키텍처](#️-아키텍처)
- [🚀 빠른 시작](#-빠른-시작)
- [⚙️ 설정](#️-설정)
- [📱 사용법](#-사용법)
- [🔧 개발자 가이드](#-개발자-가이드)
- [📂 프로젝트 구조](#-프로젝트-구조)
- [🧪 테스트](#-테스트)
- [🛠️ 트러블슈팅](#️-트러블슈팅)
- [📜 라이선스](#-라이선스)

---

## ✨ 주요 기능

### 🎥 영상 다운로드 & 업로드
- **유튜브 및 1000+ 사이트 지원** - yt-dlp 기반으로 거의 모든 영상 사이트 지원
- **해상도 선택** - 360p부터 4K까지 원하는 화질 선택
- **MP3 추출** - 오디오만 추출하여 MP3로 저장
- **대용량 파일 자동 분할** - 50MB 제한을 우회하여 어떤 크기의 영상도 업로드

### 🗄️ Bin Channel (영구 저장소)
- **영구 보관** - 모든 영상이 전용 채널에 자동 백업
- **중복 방지** - 이미 다운로드한 영상은 즉시 캐시에서 전송
- **file_id 관리** - 텔레그램 서버의 파일을 재사용하여 빠른 전송

### 🌐 웹 스트리밍
- **Direct Link** - 브라우저에서 바로 영상 재생
- **스트리밍 버튼** - 모든 영상 메시지에 "스트리밍으로 보기" 버튼 포함
- **FastAPI 기반** - 가볍고 빠른 스트리밍 서버

### 📥 플레이리스트 & 배치 다운로드
- **플레이리스트 감지** - 유튜브 재생목록 자동 인식
- **전체 다운로드** - 버튼 하나로 전체 플레이리스트 다운로드
- **개별 선택** - 원하는 영상만 골라서 다운로드
- **진행 상황 실시간 표시** - 다운로드 진행률 실시간 업데이트

---

## 🏗️ 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                         사용자 (Telegram)                          │
└─────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                        TVB Bot (bot.py)                          │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │   /start    │  │ URL Handler │  │   Callback Handler      │  │
│  │   /help     │  │             │  │   (dl, pl_all, pl_single)│  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
         │                   │                      │
         ▼                   ▼                      ▼
┌────────────────┐  ┌────────────────┐  ┌────────────────────────┐
│  downloader.py │  │   splitter.py  │  │       db.py            │
│  (yt-dlp)      │  │   (ffmpeg)     │  │    (Supabase)          │
└────────────────┘  └────────────────┘  └────────────────────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │    Bin Channel          │
              │  (Telegram Private Ch)  │
              └─────────────────────────┘
                           │
                           ▼
              ┌─────────────────────────┐
              │    Web Streaming        │
              │    (FastAPI server.py)  │
              └─────────────────────────┘
```

---

## 🚀 빠른 시작

### 사전 요구사항

- **Python 3.12+**
- **FFmpeg** (영상 분할 및 오디오 추출용)
- **Telegram Bot Token** ([@BotFather](https://t.me/BotFather)에서 생성)
- **Supabase 계정** (무료 tier 사용 가능)

### 1. 저장소 클론

```bash
git clone https://github.com/blue-code/Telegram-video-bot.git
cd Telegram-video-bot
```

### 2. 가상환경 생성 및 활성화

```bash
# Windows
python -m venv venv_win
venv_win\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. 의존성 설치

```bash
pip install -r requirements.txt
```

### 4. 환경 변수 설정

`.env.example`을 복사하여 `.env` 파일을 생성하고 필요한 값을 입력합니다:

```bash
cp .env.example .env
```

`.env` 파일 내용:

```env
# Telegram Bot Token (필수)
TELEGRAM_BOT_TOKEN=your_bot_token_here

# Supabase (필수)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key

# Bin Channel ID (선택, Pro 기능)
BIN_CHANNEL_ID=-100xxxxxxxxxx
```

### 5. 봇 실행

```bash
python -m src.bot
```

### 6. (선택) 웹 스트리밍 서버 실행

```bash
uvicorn src.server:app --reload --port 8000
```

---

## ⚙️ 설정

### Telegram Bot 생성

1. Telegram에서 [@BotFather](https://t.me/BotFather)를 찾습니다.
2. `/newbot` 명령어를 입력합니다.
3. 봇 이름과 username을 설정합니다.
4. 발급받은 토큰을 `.env` 파일에 입력합니다.

### Supabase 설정

1. [Supabase](https://supabase.com/)에서 새 프로젝트를 생성합니다.
2. SQL Editor에서 다음 테이블을 생성합니다:

```sql
CREATE TABLE videos (
    id SERIAL PRIMARY KEY,
    url TEXT NOT NULL,
    file_id TEXT NOT NULL,
    title TEXT,
    duration INTEGER,
    thumbnail TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_videos_url ON videos(url);
```

3. Project Settings > API에서 URL과 anon key를 복사하여 `.env`에 입력합니다.

### Bin Channel 설정 (Pro 기능)

1. Telegram에서 새 **비공개 채널**을 생성합니다.
2. 봇을 채널의 **관리자(Admin)**로 추가합니다 (메시지 게시 권한 필요).
3. 채널에 아무 메시지나 보내고 `run_get_id.bat`를 실행하여 채널 ID를 확인합니다.
4. 채널 ID를 `.env` 파일의 `BIN_CHANNEL_ID`에 입력합니다.

---

## 📱 사용법

### 기본 사용법

1. 봇에게 유튜브 링크를 보냅니다.
2. 원하는 화질을 선택합니다.
3. 다운로드가 완료되면 영상이 전송됩니다!

### 플레이리스트 다운로드

1. 유튜브 플레이리스트 링크를 보냅니다.
   - 예: `https://www.youtube.com/playlist?list=PLxxxxxx`
2. "전체 다운로드" 또는 개별 영상을 선택합니다.
3. 선택한 영상들이 순차적으로 다운로드됩니다.

### 스트리밍으로 보기

1. 영상이 전송되면 "🎬 스트리밍으로 보기" 버튼이 함께 나타납니다.
2. 버튼을 클릭하면 브라우저에서 영상을 바로 재생할 수 있습니다.
3. (웹 스트리밍 서버가 실행 중이어야 합니다)

### 명령어

| 명령어 | 설명 |
|--------|------|
| `/start` | 봇 시작 및 환영 메시지 |
| `/help` | 사용 방법 안내 |

---

## 🔧 개발자 가이드

### 개발 환경 설정

```bash
# 개발용 의존성 설치
pip install -r requirements.txt

# 테스트 실행
pytest tests/ -v

# 린팅
flake8 src/
```

### 주요 모듈

| 모듈 | 설명 |
|------|------|
| `src/bot.py` | 메인 봇 로직, 핸들러 정의 |
| `src/downloader.py` | yt-dlp 기반 영상 다운로드 |
| `src/splitter.py` | FFmpeg 기반 영상 분할 |
| `src/db.py` | Supabase 데이터베이스 연동 |
| `src/server.py` | FastAPI 스트리밍 서버 |

### Conductor 워크플로우

이 프로젝트는 **Conductor 워크플로우**를 사용하여 개발되었습니다.
자세한 내용은 `conductor/workflow.md`를 참조하세요.

---

## 📂 프로젝트 구조

```
telegram_video_bot/
├── src/
│   ├── bot.py              # 메인 봇 애플리케이션
│   ├── downloader.py       # yt-dlp 다운로더
│   ├── splitter.py         # FFmpeg 비디오 분할
│   ├── db.py               # Supabase 데이터베이스
│   └── server.py           # FastAPI 스트리밍 서버
├── tests/
│   ├── test_phase5.py      # 캐시 재전송 테스트
│   ├── test_phase6.py      # Bin Channel 테스트
│   └── test_phase7.py      # 스트리밍 서버 테스트
├── templates/
│   └── watch.html          # 웹 플레이어 템플릿
├── conductor/
│   ├── workflow.md         # 개발 워크플로우
│   └── tracks/
│       └── bot_mvp_20251231/
│           └── plan.md     # 프로젝트 계획
├── requirements.txt        # Python 의존성
├── .env.example            # 환경 변수 예시
├── .gitignore              # Git 제외 파일
├── run_verify.bat          # Windows 검증 스크립트
└── README.md               # 이 파일
```

---

## 🧪 테스트

### 단위 테스트 실행

```bash
# 전체 테스트
pytest tests/ -v

# 특정 테스트 파일
pytest tests/test_phase6.py -v

# 커버리지 포함
pytest tests/ --cov=src --cov-report=html
```

### 수동 테스트 (봇 검증)

```bash
# Windows
run_verify.bat

# 또는 직접 실행
python verify_phase4.py
```

봇에게 다음을 테스트해보세요:
1. 단일 유튜브 영상 링크
2. 유튜브 플레이리스트 링크
3. 이미 다운로드한 영상 (캐시 테스트)

---

## 🛠️ 트러블슈팅

### 일반적인 문제들

#### "TELEGRAM_BOT_TOKEN not found" 에러
```
해결: .env 파일이 프로젝트 루트에 있는지, 토큰이 올바른지 확인하세요.
```

#### "File too large" 에러
```
해결: MAX_FILE_SIZE 설정을 확인하세요. 기본값은 30MB입니다.
큰 파일은 자동으로 분할되어야 합니다.
```

#### FFmpeg 관련 에러
```
해결: FFmpeg가 설치되어 있고 PATH에 등록되어 있는지 확인하세요.
Windows: choco install ffmpeg
macOS: brew install ffmpeg
Ubuntu: sudo apt install ffmpeg
```

#### Bin Channel 업로드 실패
```
해결: 
1. 봇이 채널의 관리자(Admin)인지 확인
2. BIN_CHANNEL_ID가 올바른지 확인 (-100으로 시작해야 함)
3. 봇에게 "메시지 게시" 권한이 있는지 확인
```

#### 스트리밍 버튼이 작동하지 않음
```
해결: FastAPI 서버가 실행 중인지 확인하세요.
uvicorn src.server:app --reload --port 8000
```

---

## 🤝 기여하기

1. 이 저장소를 Fork합니다.
2. 새 브랜치를 생성합니다: `git checkout -b feature/amazing-feature`
3. 변경사항을 커밋합니다: `git commit -m 'Add amazing feature'`
4. 브랜치에 Push합니다: `git push origin feature/amazing-feature`
5. Pull Request를 생성합니다.

---

## 📜 라이선스

이 프로젝트는 MIT 라이선스 하에 배포됩니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.

---

## 🙏 감사의 말

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - 텔레그램 봇 API 라이브러리
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - 영상 다운로드 엔진
- [FFmpeg](https://ffmpeg.org/) - 멀티미디어 처리
- [FastAPI](https://fastapi.tiangolo.com/) - 웹 프레임워크
- [Supabase](https://supabase.com/) - 백엔드 서비스

---

<p align="center">
  Made with ❤️ by blue-code
</p>
