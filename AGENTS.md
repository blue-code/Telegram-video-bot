# Repository Guidelines

## Project Structure & Module Organization
- `src/` holds the bot and API code (`bot.py`, `server.py`, `downloader.py`, `splitter.py`, `db.py`).
- `tests/` contains pytest suites (async tests live here).
- `templates/` and `static/` serve the FastAPI/Jinja2 web UI.
- `migrations/` and `conductor/` track database/workflow artifacts.
- `downloads/` and `uploads/` are runtime output folders; keep them out of commits.

## Build, Test, and Development Commands
- `pip install -r requirements.txt` installs Python dependencies.
- `python -m src.bot` starts the Telegram bot.
- `uvicorn src.server:app --reload --port 8000` runs the FastAPI streaming server.
- `pytest` or `pytest tests/ -v` runs the test suite.
- `pytest --cov=src --cov-report=html` generates coverage reports.

## Coding Style & Naming Conventions
- Follow Google Python Style: 4-space indentation, 80-char lines, and clear docstrings.
- Naming: `snake_case` for functions/variables, `PascalCase` for classes, `ALL_CAPS` for constants.
- Prefer `async/await`; wrap blocking calls with `asyncio.run_in_executor`.
- No formatter is enforced; keep imports grouped (stdlib, third-party, local).

## Testing Guidelines
- Frameworks: `pytest`, `pytest-asyncio`, `pytest-cov`.
- Test files follow `tests/test_<module>.py`.
- Mark async tests with `@pytest.mark.asyncio` and mock external services (Telegram, Supabase).
- Aim for >80% coverage on changed modules.

## Commit & Pull Request Guidelines
- Use conventional commit subjects like `feat(bot):`, `fix(db):`, `test(api):`, `chore(ci):`.
- Keep subjects imperative and concise; merge commits are acceptable for PRs.
- PRs should explain the change, link issues, and include test results; add screenshots for UI/template changes.

## Configuration & Secrets
- Use a local `.env` with `TELEGRAM_BOT_TOKEN`, `SUPABASE_URL`, `SUPABASE_KEY`, and optional `BIN_CHANNEL_ID`.
- Never commit secrets or generated media artifacts.

## 추가 커뮤니케이션 및 커밋 규칙
- 모든 주고받는 답변은 한글로 진행한다.
- 모든 작업이 끝난 후에, 수정한 파일에 한정하여 커밋을 진행한다.
- 커밋 메시지에는 유형별 접두어를 붙인다.
  - 새로운 기능: `feat :`
  - 에러 수정: `fix :`
  - 리팩토링: `refactor :`
  - 문서 수정: `docs :`