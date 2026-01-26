# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Telegram Video Bot (TVB)** is a multi-purpose Telegram bot and web platform that downloads videos from YouTube and 1000+ sites, manages eBooks (EPUB), comic books (CBZ/ZIP), and provides web-based streaming with a modern interface. Users interact via Telegram bot or web dashboard.

## Technology Stack

- **Language:** Python 3.12+
- **Bot Framework:** `python-telegram-bot` (async)
- **Video Download:** `yt-dlp`
- **Video Processing:** `ffmpeg`
- **Database:** Supabase (PostgreSQL) via async client
- **Web Framework:** FastAPI with Jinja2 templates
- **Image Processing:** Pillow (comic book thumbnails)
- **Testing:** pytest with pytest-asyncio and pytest-cov

## Development Commands

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment variables in .env
# Required: TELEGRAM_BOT_TOKEN, SUPABASE_URL, SUPABASE_KEY, BIN_CHANNEL_ID
```

### Running the Application
```bash
# Run Telegram bot
python -m src.bot

# Run web server (development)
uvicorn src.server:app --reload --port 8000

# Run web server (production)
uvicorn src.server:app --host 0.0.0.0 --port 8000 --workers 4

# Windows all-in-one (bot + web server)
start_all.bat
```

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_phase7.py -v

# Run in CI mode (non-interactive)
CI=true pytest
```

### Database Migrations
```bash
# Apply migrations manually via Supabase SQL Editor
# Migration files located in migrations/

# Migrate existing comics from files table
python migrate_existing_comics.py
```

## Architecture

### System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    User Interface Layer                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────┐  │
│  │  Telegram Bot    │  │  Web Dashboard   │  │  Mobile Web   │  │
│  │  (src/bot.py)    │  │  (templates/)    │  │  (Responsive) │  │
│  └──────────────────┘  └──────────────────┘  └───────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Application Layer                            │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────────┐  │
│  │  downloader.py │  │   splitter.py  │  │  comic_parser.py │  │
│  │    (yt-dlp)    │  │    (ffmpeg)    │  │    (Pillow)      │  │
│  └────────────────┘  └────────────────┘  └──────────────────┘  │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────────┐  │
│  │  transcoder.py │  │ user_manager.py│  │link_shortener.py │  │
│  │  (re-encoding) │  │  (quota/tier)  │  │  (short links)   │  │
│  └────────────────┘  └────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Data Layer                                  │
│  ┌────────────────┐  ┌────────────────┐  ┌──────────────────┐  │
│  │   db.py        │  │  Bin Channel   │  │  Local Storage   │  │
│  │  (Supabase)    │  │  (Telegram)    │  │  (download_cache)│  │
│  └────────────────┘  └────────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### Core Modules

**src/bot.py** - Telegram bot entry point
- Command handlers: `/start`, `/help`, `/library`, `/search`, `/stats`, `/quota`
- Message handler: URL detection via regex
- Callback handlers: Quality selection, playlist handling, favorites
- Admin commands: `/grant_premium`

**src/server.py** - FastAPI web server (3600+ lines)
- Video streaming endpoints: `/watch/{short_id}`, `/stream/{file_id}`
- Gallery pages: `/gallery/{user_id}`, `/dashboard/{user_id}`
- eBook reader: `/read/{file_id}`, EPUB rendering with progress tracking
- Comic book viewer: `/comics/{user_id}`, `/comic_reader/{file_id}`
- File management: Upload, download, delete with multi-file ZIP support
- API endpoints: RESTful API with X-API-Key authentication
- Video transcoding: Real-time H.264/AAC encoding for mobile compatibility

**src/downloader.py** - Video download engine
- `extract_video_info(url)`: Async wrapper around yt-dlp
- Playlist support with individual video selection
- Format filtering: MP4 video + MP3 audio extraction
- Thumbnail extraction and caching

**src/splitter.py** - Video processing
- `split_video(file_path, max_size_bytes)`: Splits videos >2GB for Telegram
- Uses ffmpeg with `-c copy` for fast stream copying
- Automatic cleanup of temporary files

**src/comic_parser.py** - Comic book metadata extraction
- `is_comic_book(file_path)`: Detects CBZ/ZIP with 80%+ image ratio
- `extract_comic_metadata(file_path)`: Extracts series, volume, page count
- Series pattern matching: Recognizes "야와라 01권", "OnePiece vol.1" formats
- Thumbnail generation with Pillow (274x400 WebP/JPEG)
- `get_page_image(file_path, page_num)`: Page-by-page extraction for viewer

**src/db.py** - Supabase database operations (1250+ lines)
- Video CRUD: `save_video_metadata()`, `get_user_videos()`, `delete_video()`
- User management: `get_or_create_user()`, `update_user_tier()`, quota tracking
- Favorites: `add_favorite()`, `remove_favorite()`, `get_favorites()`
- Short links: `get_or_create_short_link()`, view tracking with analytics
- eBook: `get_books()`, `save_reading_progress()`, EPUB metadata storage
- Comics: `save_comic_metadata()`, `get_comic_series()`, progress tracking
- Files: Generic file management with filtering, search, pagination

**src/transcoder.py** - Video re-encoding
- Real-time transcoding to H.264/AAC for mobile compatibility
- Resolution selection: 720p, 1080p, original
- FFmpeg-based streaming with cleanup
- Encoded video caching and management

**src/user_manager.py** - User tier and quota system
- Tier levels: FREE (10 videos/day), PREMIUM (unlimited)
- Daily quota enforcement with reset at midnight
- Usage statistics and analytics

**src/link_shortener.py** - Short link generation
- Generates 6-character short IDs for videos
- Collision detection and retry logic
- View tracking with IP and User-Agent analytics

### Data Flow Examples

#### Video Download Flow
1. User sends URL → `handle_message()` validates URL
2. Bot calls `extract_video_info(url)` → returns formats
3. Bot presents inline keyboard with quality options
4. User selects quality → `handle_callback()` parses `dl|video_id|format_id|quality`
5. Bot downloads → splits if >2GB → uploads to Bin Channel
6. Saves file_id to Supabase → creates short link
7. Sends video to user with streaming button

#### Comic Book Upload Flow
1. User uploads ZIP file → `server.py` receives file
2. `is_comic_book()` checks image ratio (80%+ images)
3. `extract_comic_metadata()` parses filename for series/volume
4. Generates thumbnail (base64 encoded for JSON)
5. Saves to permanent storage: `download_cache/comics/{user_id}/`
6. Inserts metadata into `comics` table with file_path
7. Displays in `/comics/{user_id}` gallery

#### EPUB Reading Flow
1. User clicks book → `/read/{file_id}` loads reader
2. EPUB file extracted in memory with `ebooklib`
3. HTML rendered with custom CSS theme
4. JavaScript tracks reading position (CFI - Canonical Fragment Identifier)
5. Progress saved to `reading_progress` table on page turn
6. Next session resumes from saved position

### Database Schema (Supabase PostgreSQL)

**videos** - Video metadata and file IDs
```sql
- id, url, file_id, title, duration, thumbnail
- user_id, metadata (JSONB), views, short_id
- created_at
```

**users** - User management and quotas
```sql
- id, telegram_user_id, username, full_name
- tier (FREE/PREMIUM), daily_quota, quota_used, quota_reset_at
```

**favorites** - User favorite videos
```sql
- user_id, video_id, created_at
```

**shared_links** - Short link mapping
```sql
- id, short_id, file_id, video_id, user_id, created_at
```

**views** - View tracking and analytics
```sql
- id, video_id, short_id, ip_address, user_agent, created_at
```

**files** - Generic file storage
```sql
- id, user_id, file_id, file_name, file_size, mime_type
- file_path, metadata (JSONB), created_at
```

**books** - EPUB metadata
```sql
- id, file_id, user_id, title, author, cover_file_id, page_count
```

**reading_progress** - EPUB reading position
```sql
- user_id, file_id, current_page, current_cfi, settings (JSONB)
```

**comics** - Comic book metadata
```sql
- id, file_id, user_id, title, series, volume, folder
- page_count, metadata (JSONB with cover_base64)
```

**comic_progress** - Comic reading position
```sql
- user_id, file_id, current_page, settings (JSONB)
```

**comic_favorites** - Comic favorites
```sql
- user_id, file_id
```

## Key Features Implementation

### Comic Book Viewer (`templates/comic_reader.html`)
- Dual mode: Page-by-page (comic mode) + Vertical scroll (webtoon mode)
- Reading direction: LTR/RTL toggle
- Double-page auto-split for portrait screens (aspect ratio >1.5:1)
- Canvas-based image splitting with GPU acceleration
- Auto-navigation between volumes in series
- Progress saving with page number tracking
- Favorites and download support
- Lazy loading for webtoon mode with Intersection Observer
- Touch gestures and keyboard shortcuts

### EPUB Reader (`templates/epub_reader.html`)
- Full EPUB rendering with CSS theming (sepia, dark, light)
- Font size adjustment and family selection
- Progress tracking with CFI (Canonical Fragment Identifier)
- Chapter navigation with table of contents
- Touch-friendly page turning
- Bookmark support
- Reading statistics

### Responsive Navigation (`static/nav.js`)
- Mobile hamburger menu (768px breakpoint)
- Event-driven toggle without overlay
- Outside click detection for auto-close
- iPhone Safari compatible
- Clean z-index layering (toggle: 10001, menu: 10000)

### Video Transcoding
- Automatic mobile detection (User-Agent parsing)
- On-demand H.264/AAC encoding via FFmpeg
- Progress tracking during encoding
- Cached encoded videos for repeat access
- Cleanup of old encoded files (7-day retention)

## Common Patterns

### Async Context
All bot handlers, database operations, and file processing are async:
```python
async def function_name():
    await async_operation()
```

### Blocking Operations
Wrap blocking calls (yt-dlp, ffmpeg, Pillow) in executor:
```python
loop = asyncio.get_running_loop()
result = await loop.run_in_executor(None, blocking_function, args)
```

### Callback Data Format
Telegram inline button callbacks use pipe-delimited strings:
```python
# Format: action|param1|param2|...
callback_data = "dl|video_id|format_id|1080p"
parts = callback_data.split('|')
action, video_id, format_id, quality = parts
```

### Base64 Image Encoding
Thumbnails stored as base64 in JSONB for JSON serialization:
```python
import base64
cover_base64 = base64.b64encode(image_bytes).decode('utf-8')
metadata = {"cover_base64": cover_base64}

# Decode when serving
image_bytes = base64.b64decode(metadata["cover_base64"])
```

### Error Handling
- Log errors with context: `logger.error(f"Error message: {e}")`
- User-facing messages in Korean via `reply_text()` or `edit_message_text()`
- HTTP exceptions in FastAPI: `raise HTTPException(status_code=404, detail="Not found")`

## Environment Variables

Required in `.env`:
```env
# Telegram (Required)
TELEGRAM_BOT_TOKEN=your_bot_token
BIN_CHANNEL_ID=-100xxxxxxxxxx

# Supabase (Required)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_supabase_anon_key

# Optional
BASE_URL=http://localhost:8000
ADMIN_USER_ID=your_telegram_user_id
API_KEY=your_secure_api_key
DEFAULT_USER_ID=41509535
```

## File Storage Patterns

### Temporary Files
- Downloaded videos: `download_cache/` (auto-cleanup after upload)
- Encoded videos: `encoded_cache/` (7-day retention)
- Temporary uploads: System temp directory with UUID prefix

### Permanent Storage
- Comic books: `download_cache/comics/{user_id}/{hash}_{filename}.zip`
- EPUB files: Stored in Telegram Bin Channel, retrieved on-demand
- Thumbnails: Base64 in database JSONB or Telegram file_id

## Testing Patterns

- Use `pytest-asyncio` for async functions with `@pytest.mark.asyncio`
- Mock Telegram API calls with `unittest.mock.AsyncMock`
- Mock Supabase responses with fixtures
- Test both success and error paths
- Coverage target: >80%

## Mobile Compatibility

### iPhone Safari Considerations
- Use `-webkit-` prefixes for backdrop-filter, transform
- Avoid complex CSS animations (use display: none/flex instead)
- `pointer-events` management for touch events
- Explicit `z-index` values (avoid auto)
- `<meta name="viewport">` for responsive scaling

### Responsive Breakpoints
- Mobile: 0-768px (1-column layouts, hamburger menu)
- Tablet: 768-1024px (2-3 column grids)
- Desktop: 1024px+ (full layouts)

## Known Issues

### Supabase Migration
Project migrated from MongoDB Atlas to Supabase PostgreSQL. Old MongoDB references in legacy code should be ignored.

### File Path Storage
Comic books require `file_path` column in `files` table for page-by-page reading. Migration: `ALTER TABLE files ADD COLUMN file_path TEXT;`

### Pillow Dependency
Required for comic book thumbnail generation. Ensure `Pillow>=10.0.0` in requirements.txt.

## Code Style

- **Line length:** 120 characters (relaxed from 80 for web templates)
- **Naming:** `snake_case` for functions/variables, `PascalCase` for classes
- **Docstrings:** Required for public functions
- **Type hints:** Encouraged but not strictly enforced
- **Imports:** Grouped (stdlib, third-party, local)
- **User messages:** Korean language for bot interactions
- **Commit format:** Conventional commits (`feat:`, `fix:`, `refactor:`)

## Current Status

**Implemented Features:**
- ✅ Video download and streaming (YouTube + 1000+ sites)
- ✅ Playlist support with individual selection
- ✅ Bin Channel integration (permanent storage)
- ✅ Web player with modern UI and keyboard shortcuts
- ✅ Video transcoding for mobile compatibility
- ✅ User management with FREE/PREMIUM tiers
- ✅ Daily quota system
- ✅ EPUB reader with progress tracking
- ✅ Comic book viewer (CBZ/ZIP) with dual modes
- ✅ File management with search, filters, multi-download
- ✅ Responsive web interface with mobile support
- ✅ RESTful API with authentication
- ✅ Short link generation and analytics

**Recent Additions:**
- ✅ Comic book series auto-grouping by filename patterns
- ✅ Responsive hamburger menu for mobile navigation
- ✅ iPhone Safari compatibility improvements
- ✅ Base64 thumbnail caching for JSON serialization
- ✅ File deletion API fix (422 error resolved)
