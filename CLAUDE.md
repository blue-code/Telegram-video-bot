# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Telegram Video Bot (TVB)** is an intelligent Telegram bot that downloads videos from YouTube and other sources, processes them for Telegram's file size limits, and stores them in MongoDB Atlas for instant re-streaming. Users send URLs, select quality, and the bot handles downloading, splitting (if needed), and uploading to Telegram.

## Technology Stack

- **Language:** Python 3.12+
- **Bot Framework:** `python-telegram-bot` (async)
- **Video Download:** `yt-dlp`
- **Video Processing:** `ffmpeg`
- **Database:** MongoDB Atlas via `motor` (async MongoDB driver)
- **Web Framework:** FastAPI (planned for dashboard)
- **Testing:** pytest with pytest-asyncio and pytest-cov

## Development Commands

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment variables in .env
# Required: TELEGRAM_BOT_TOKEN, MONGO_URI
```

### Running Tests
```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_bot_interaction.py

# Run in CI mode (non-interactive)
CI=true pytest
```

### Running the Bot
```bash
python -m src.bot
```

### Running Phase Verification Scripts
```bash
# Verify completed phases
python verify_phase1.py  # Database setup
python verify_phase2.py  # Media processing
python verify_phase3.py  # Bot interaction
```

## Architecture

### Core Modules

**src/bot.py** - Main bot entry point and handlers
- Command handlers: `/start`, `/help`
- Message handler: URL detection via regex
- Callback handler: Inline button interactions (quality selection)
- Integrates with `downloader` and `db` modules

**src/downloader.py** - Video information extraction
- `extract_video_info(url)`: Async wrapper around yt-dlp
- Returns video metadata: id, title, duration, thumbnail, formats
- Uses `asyncio.run_in_executor` to avoid blocking

**src/splitter.py** - Video splitting for Telegram limits
- `get_video_duration(file_path)`: Uses ffprobe to get duration
- `split_video(file_path, max_size_bytes)`: Splits videos exceeding 2GB into chunks
- Uses ffmpeg with `-c copy` for fast stream copying

**src/db.py** - MongoDB operations
- `get_database()`: Returns Motor async client instance
- `save_video_metadata(data)`: Stores video info and File ID
- `get_video_by_url(url)`: Retrieves cached video by URL
- `get_video_by_file_id(file_id)`: Retrieves video by Telegram File ID
- Uses `tlsAllowInvalidCertificates=True` parameter for OpenSSL 3.x compatibility (fixes TLSV1_ALERT_INTERNAL_ERROR)

### Data Flow

1. User sends URL → `handle_message()` extracts URL via regex
2. Bot calls `extract_video_info(url)` to get formats
3. Bot presents inline keyboard with quality options (filtered to unique heights, MP4 only)
4. User selects quality → `handle_callback()` receives callback data format: `dl|video_id|format_id|quality`
5. Bot downloads video, splits if >2GB, uploads to Telegram, saves File ID to MongoDB
6. For repeat requests, bot checks `get_video_by_url()` and resends cached File ID

### MongoDB Schema

**videos collection:**
```python
{
    "url": str,           # Original video URL
    "file_id": str,       # Telegram File ID for instant resend
    "title": str,         # Video title
    "duration": float,    # Duration in seconds
    "thumbnail": str,     # Thumbnail URL
    # Additional metadata as needed
}
```

## Workflow Integration

This project follows a strict **Test-Driven Development (TDD)** workflow managed via `conductor/` directory:

- **Plan:** All tasks tracked in `conductor/tracks/bot_mvp_20251231/plan.md`
- **Phases:** Development organized into phases with checkpoints
- **Task Format:** Tasks marked `[ ]` (pending), `[~]` (in progress), `[x] <commit_sha>` (completed)
- **Git Notes:** Task summaries attached to commits via `git notes`
- **Verification:** Each phase ends with automated tests + manual verification protocol

### Workflow Requirements

1. **Select task** from plan.md in order
2. **Write failing tests** first (Red phase)
3. **Implement** minimum code to pass (Green phase)
4. **Verify coverage** (target >80%)
5. **Commit** code changes with conventional commit format
6. **Attach git note** with task summary to commit
7. **Update plan.md** with commit SHA and mark task complete
8. **Commit plan.md** update with `conductor(plan):` prefix

### Phase Completion Protocol

After completing a phase:
1. Ensure all phase changes have test coverage
2. Run automated tests with announcement
3. Provide detailed manual verification plan
4. Await user confirmation
5. Create checkpoint commit with `conductor(checkpoint):` prefix
6. Attach verification report via git notes
7. Update plan.md with checkpoint SHA

## Code Style

Follows **Google Python Style Guide** (see `conductor/code_styleguides/python.md`):

- **Line length:** 80 characters max
- **Indentation:** 4 spaces (no tabs)
- **Naming:** `snake_case` for functions/variables, `PascalCase` for classes, `ALL_CAPS` for constants
- **Docstrings:** Required for all public functions/classes, use `"""triple quotes"""`
- **Type annotations:** Strongly encouraged
- **Imports:** Grouped (stdlib, third-party, local) on separate lines
- **Async patterns:** Use `async/await` throughout; wrap blocking calls with `run_in_executor`

## Testing Patterns

- Use `pytest-asyncio` for async test functions
- Mock external services (Telegram API, MongoDB) using `unittest.mock` or pytest fixtures
- Test file naming: `test_<module_name>.py`
- Verify both success and failure cases
- Use `httpx` for async HTTP testing (FastAPI endpoints)

## Environment Variables

Required in `.env`:
- `TELEGRAM_BOT_TOKEN`: Bot token from @BotFather
- `MONGO_URI`: MongoDB Atlas connection string

## Common Patterns

### Async Context
All bot handlers and media processing functions are async. Use:
```python
async def function_name():
    # Async operations
    await some_async_call()
```

### Blocking Operations
Wrap blocking calls (yt-dlp, ffmpeg) in executor:
```python
loop = asyncio.get_running_loop()
result = await loop.run_in_executor(None, blocking_function)
```

### Inline Keyboards
Callback data format: `action|param1|param2|...`
Split with `data.split('|')` in callback handler

### Error Handling
- Log errors with `logging.error()`
- Send user-friendly Korean messages via `edit_message_text()` or `reply_text()`

## Current Status (as of Phase 3 completion)

**Completed:**
- MongoDB Atlas integration with Motor
- Video info extraction via yt-dlp
- Video splitting with ffmpeg (2GB chunks)
- Basic bot commands (`/start`, `/help`)
- URL detection and quality selection menu
- Inline keyboard callbacks

**TODO (Phase 4-5):**
- Download progress tracking with live updates
- Telegram file upload with File ID storage
- Cached video re-streaming

## Important Notes

- Bot runs on macOS locally (dev environment) with Python 3.12 and OpenSSL 3.5.0
- MongoDB Atlas connection uses `tlsInsecure=true` workaround for OpenSSL 3.x TLS handshake compatibility
- All user-facing messages are in Korean
- Inline buttons filter formats to unique heights, MP4 only, plus MP3 audio-only option
- Commit messages use conventional commits: `feat(scope):`, `fix(scope):`, `test(scope):`
- Plan updates use `conductor(plan):` or `conductor(checkpoint):` prefix

## Known Issues & Workarounds

**CRITICAL: OpenSSL 3.5.0 TLS Handshake Error with MongoDB Atlas**

**Problem:**
`TLSV1_ALERT_INTERNAL_ERROR` when performing MongoDB Atlas queries on macOS with OpenSSL 3.5.0 and Python 3.12.

**Root Cause:**
OpenSSL 3.5.0 removed legacy TLS cipher suites that some MongoDB Atlas clusters still use. This creates an incompatibility that cannot be resolved through pymongo/motor configuration alone.

**Current Status:**
- ✅ Bot starts successfully
- ✅ Database connection initializes
- ❌ Database queries fail with SSL handshake error when bot receives messages

**Workarounds (choose one):**

1. **Use Local MongoDB (Recommended for Development)**
   ```bash
   # Install MongoDB locally via Homebrew
   brew install mongodb-community
   brew services start mongodb-community

   # Update .env
   MONGO_URI=mongodb://localhost:27017
   ```

2. **Use Docker MongoDB**
   ```bash
   docker run -d -p 27017:27017 --name mongodb mongo:latest
   # Update .env: MONGO_URI=mongodb://localhost:27017
   ```

3. **Contact MongoDB Atlas Support**
   - Request TLS configuration upgrade to support OpenSSL 3.x
   - Upgrade to a newer cluster tier with modern TLS support

4. **Use Python 3.11 with Older OpenSSL**
   ```bash
   # Install Python 3.11 which uses OpenSSL 3.0.x
   brew install python@3.11
   python3.11 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

**Temporary Development Bypass:**
The code in `src/db.py` attempts to use `tlsAllowInvalidCertificates=true`, but this parameter is not honored by pymongo 4.15.5 with OpenSSL 3.5.0. A code-only fix is not currently possible.
