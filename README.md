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
- **모던 플레이어** - PiP, 극장 모드, 속도 조절, 키보드 단축키 지원

### 📥 플레이리스트 & 배치 다운로드
- **플레이리스트 감지** - 유튜브 재생목록 자동 인식
- **전체 다운로드** - 버튼 하나로 전체 플레이리스트 다운로드
- **개별 선택** - 원하는 영상만 골라서 다운로드
- **진행 상황 실시간 표시** - 다운로드 진행률 실시간 업데이트

### 📚 라이브러리 관리
- **영상 검색** - 제목으로 영상 빠르게 찾기
- **즐겨찾기** - 자주 보는 영상 즐겨찾기 추가
- **최근 목록** - 최근 다운로드한 영상 바로 접근
- **페이지네이션** - 대량의 영상도 편리하게 탐색

### 👤 사용자 관리 & 쿼터
- **무료/프리미엄 등급** - 사용자별 등급 시스템
- **일일 다운로드 쿼터** - 무료 사용자 제한 관리
- **통계 대시보드** - 개인 다운로드 통계 확인
- **관리자 명령어** - 프리미엄 등급 부여 기능

### 🎬 웹 갤러리
- **반응형 그리드** - 모든 디바이스에 최적화
- **실시간 검색** - 빠른 영상 찾기
- **필터 기능** - 전체/즐겨찾기/최근 필터링
- **썸네일 미리보기** - 영상 썸네일과 메타데이터 표시

### 🔌 RESTful API
- **완전한 CRUD** - 영상 생성/조회/수정/삭제
- **API 인증** - X-API-Key 헤더 기반 보안
- **통계 엔드포인트** - 프로그래매틱 데이터 접근
- **CORS 지원** - 크로스 오리진 요청 허용

### 🔗 단축 링크
- **자동 생성** - 모든 영상에 짧은 공유 링크 생성
- **조회수 추적** - 웹 플레이어 조회수 자동 카운팅
- **분석 데이터** - IP, User-Agent 기반 시청 분석

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

#### 기본 명령어
| 명령어 | 설명 | 예시 |
|--------|------|------|
| `/start` | 봇 시작 및 환영 메시지 | `/start` |
| `/help` | 사용 방법 안내 | `/help` |

#### 라이브러리 관리 명령어
| 명령어 | 설명 | 예시 |
|--------|------|------|
| `/library` 또는 `/list` | 내 영상 목록 보기 (페이지네이션 지원) | `/library` |
| `/search <키워드>` | 영상 제목으로 검색 | `/search 뮤직비디오` |
| `/recent` | 최근 다운로드한 영상 (5개) | `/recent` |
| `/favorites` | 즐겨찾기 목록 보기 | `/favorites` |

#### 통계 및 정보 명령어
| 명령어 | 설명 | 예시 |
|--------|------|------|
| `/stats` | 내 통계 보기 (다운로드 수, 저장 용량 등) | `/stats` |
| `/quota` | 남은 다운로드 횟수 확인 | `/quota` |
| `/popular` | 인기 영상 TOP 10 | `/popular` |
| `/queue` | 현재 다운로드 큐 상태 보기 | `/queue` |

#### 관리자 명령어
| 명령어 | 설명 | 예시 |
|--------|------|------|
| `/grant_premium <user_id>` | 사용자에게 프리미엄 등급 부여 (관리자 전용) | `/grant_premium 123456789` |

---

## 🌐 웹 인터페이스

### 비디오 플레이어 (Watch Page)

URL 형식: `http://your-domain/watch/{short_id}`

**기능:**
- 🎬 HTML5 비디오 플레이어
- 📊 메타데이터 표시 (제목, 재생시간, 조회수, 업로드 날짜)
- ⬇️ 다운로드 버튼 (직접 파일 다운로드)
- 🔗 공유 버튼 (URL 복사 또는 네이티브 공유)
- 🎮 재생 속도 조절 (0.5x ~ 2x)
- 📺 Picture-in-Picture 모드
- 🖥️ 극장 모드
- ⌨️ 키보드 단축키 지원
  - `Space` 또는 `K`: 재생/일시정지
  - `F`: 전체화면
  - `←` / `→`: 5초 앞뒤로
  - `↑` / `↓`: 볼륨 조절
- 📱 모바일 최적화 반응형 디자인
- 🎨 현대적인 다크 테마 UI

### 갤러리 페이지 (Gallery)

URL 형식: `http://your-domain/gallery/{user_id}`

**기능:**
- 🖼️ 반응형 그리드 레이아웃
  - 모바일: 1열
  - 태블릿: 3열
  - 데스크톱: 4열
- 🔍 실시간 검색 기능
- 🎯 필터 버튼 (전체 / 즐겨찾기 / 최근)
- 📷 썸네일 미리보기
- ⏱️ 재생시간 오버레이
- 👁️ 조회수 표시
- 🎨 호버 효과 (확대 & 그림자)
- 📭 비어있을 때 안내 메시지

---

## 🔌 REST API 문서

### 공개 엔드포인트 (인증 불필요)

#### Health Check
```http
GET /health
```
**응답:**
```json
{
  "status": "healthy",
  "service": "TVB API",
  "version": "1.0.0"
}
```

#### Short Link 해석
```http
GET /api/resolve/{short_id}
```
**응답:**
```json
{
  "success": true,
  "data": {
    "file_id": "...",
    "title": "Video Title",
    "duration": 180,
    "views": 42,
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

#### 조회수 증가
```http
POST /api/increment-view/{short_id}
```
**응답:**
```json
{
  "success": true,
  "message": "View count incremented"
}
```

#### 비디오 다운로드
```http
GET /download/{short_id}
```
비디오 파일을 직접 다운로드합니다.

---

### 보호된 엔드포인트 (API Key 필요)

**헤더:**
```
X-API-Key: your_api_key_here
```

`.env` 파일에 `API_KEY` 설정:
```env
API_KEY=your_secure_api_key_here
```

#### 비디오 목록 조회
```http
GET /api/videos?user_id={user_id}&page=1&per_page=20&filter=all&search=keyword
```
**쿼리 파라미터:**
- `user_id` (필수): 사용자 ID
- `page` (선택): 페이지 번호 (기본값: 1)
- `per_page` (선택): 페이지당 결과 수 (기본값: 20)
- `filter` (선택): 필터 타입 (all, favorites, recent)
- `search` (선택): 검색 키워드

**응답:**
```json
{
  "success": true,
  "data": [...],
  "page": 1,
  "per_page": 20,
  "total": 10
}
```

#### 비디오 상세 정보
```http
GET /api/videos/{video_id}
```
**응답:**
```json
{
  "success": true,
  "data": {
    "id": 1,
    "title": "Video Title",
    "duration": 180,
    "views": 42,
    ...
  }
}
```

#### 비디오 삭제
```http
DELETE /api/videos/{video_id}?user_id={user_id}
```
**응답:**
```json
{
  "success": true,
  "message": "Video deleted"
}
```

#### 사용자 통계
```http
GET /api/stats/{user_id}
```
**응답:**
```json
{
  "success": true,
  "data": {
    "user": {...},
    "video_count": 10,
    "total_storage": 1073741824,
    "favorites_count": 5
  }
}
```

#### 즐겨찾기 목록
```http
GET /api/favorites/{user_id}
```
**응답:**
```json
{
  "success": true,
  "data": [...]
}
```

---

## 🗄️ 데이터베이스 마이그레이션

프로젝트는 Supabase를 사용하며, 마이그레이션 파일이 `migrations/` 디렉토리에 있습니다.

### 마이그레이션 목록

1. `001_add_shared_links.sql` - 공유 링크 테이블
2. `002_add_favorites.sql` - 즐겨찾기 테이블
3. `003_add_users.sql` - 사용자 관리 테이블
4. `004_add_user_id_to_videos.sql` - 비디오 테이블에 user_id 추가
5. `005_add_view_tracking.sql` - 조회수 추적 컬럼
6. `006_add_views_table.sql` - 조회수 분석 테이블

### 마이그레이션 실행 방법

```bash
# 마이그레이션 스크립트 실행
python migrations/run_migrations.py
```

**중요:** Supabase Python 클라이언트는 직접 SQL 실행을 지원하지 않으므로, 위 스크립트를 실행하면 SQL 문이 출력됩니다. 이를 Supabase Dashboard의 SQL Editor에 복사하여 실행하세요.

**단계:**
1. 마이그레이션 스크립트 실행하여 SQL 출력
2. Supabase Dashboard > SQL Editor 접속
3. 출력된 SQL을 순서대로 복사 & 실행 (001부터 006까지)

---

## 🚀 프로덕션 배포 가이드

### 환경 변수 설정

프로덕션 환경에서 필요한 모든 환경 변수:

```env
# 필수
TELEGRAM_BOT_TOKEN=your_bot_token
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_key

# 선택 (프로덕션 권장)
BIN_CHANNEL_ID=-100xxxxxxxxxx
BASE_URL=https://your-domain.com
ADMIN_USER_ID=your_telegram_user_id
API_KEY=your_secure_api_key
```

### 배포 체크리스트

- [ ] 모든 환경 변수 설정 완료
- [ ] Supabase 데이터베이스 마이그레이션 완료
- [ ] FFmpeg 설치 확인
- [ ] Python 3.12+ 설치 확인
- [ ] 의존성 설치: `pip install -r requirements.txt`
- [ ] Bin Channel 설정 및 봇 관리자 권한 부여
- [ ] 방화벽 규칙 확인 (포트 8000 열기)
- [ ] SSL/TLS 인증서 설정 (HTTPS 권장)
- [ ] 로그 모니터링 시스템 설정
- [ ] 백업 전략 수립

### 서버 실행

**봇 서버:**
```bash
# 프로덕션 모드로 봇 실행
python -m src.bot
```

**웹 서버:**
```bash
# Uvicorn으로 FastAPI 서버 실행
uvicorn src.server:app --host 0.0.0.0 --port 8000 --workers 4
```

**프로세스 매니저 사용 (권장):**
```bash
# systemd, supervisor, PM2 등 사용
# 예: systemd 서비스 파일
[Unit]
Description=TVB Bot
After=network.target

[Service]
Type=simple
User=tvb
WorkingDirectory=/path/to/Telegram-video-bot
ExecStart=/usr/bin/python3 -m src.bot
Restart=always

[Install]
WantedBy=multi-user.target
```

### 성능 최적화

- **Redis 캐싱**: 자주 조회되는 데이터 캐싱
- **CDN 사용**: 정적 파일 및 썸네일 제공
- **로드 밸런싱**: 여러 웹 서버 인스턴스 운영
- **데이터베이스 인덱싱**: 쿼리 성능 최적화
- **큐 시스템**: 대량 다운로드 처리

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
│   ├── server.py           # FastAPI 스트리밍 서버 & REST API
│   ├── user_manager.py     # 사용자 관리 & 쿼터
│   ├── link_shortener.py   # 단축 링크 생성
│   ├── queue_manager.py    # 다운로드 큐 관리
│   └── api_auth.py         # API 인증
├── templates/
│   ├── watch.html          # 웹 플레이어 템플릿
│   ├── gallery.html        # 갤러리 페이지
│   └── error.html          # 에러 페이지
├── migrations/
│   ├── 001_add_shared_links.sql
│   ├── 002_add_favorites.sql
│   ├── 003_add_users.sql
│   ├── 004_add_user_id_to_videos.sql
│   ├── 005_add_view_tracking.sql
│   ├── 006_add_views_table.sql
│   └── run_migrations.py   # 마이그레이션 실행 스크립트
├── tests/
│   ├── test_phase5.py      # 캐시 재전송 테스트
│   ├── test_phase6.py      # Bin Channel 테스트
│   └── test_phase7.py      # 스트리밍 서버 테스트
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
