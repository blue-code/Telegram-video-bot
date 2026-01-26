# Implementation Plan: Universal Series & Bookmarks

## Phase 1: Database & Backend Core [checkpoint: detected]
- [x] Task: Schema Design & Migration
    - [x] Create `migrations/20250124_add_bookmarks_series.sql` for `bookmarks`, `series`, `series_items`, `read_progress` tables.
- [x] Task: Database Layer
    - [x] Implement `src/db_bookmarks_series.py` with async CRUD operations.
- [x] Task: API Layer
    - [x] Implement `src/api_bookmarks_series.py` with FastAPI routes.
    - [x] Register router in `src/server.py`.
- [x] Task: Conductor - User Manual Verification 'Phase 1'

## Phase 2: Frontend Implementation [checkpoint: detected]
- [x] Task: JS Client
    - [x] Create `static/bookmarks-series.js` to handle API calls and UI updates.
- [x] Task: UI Integration (Series)
    - [x] Update `templates/books_series.html` to display manual series.
    - [x] Add controls to create/manage series.
- [x] Task: UI Integration (Bookmarks)
    - [x] Integrate bookmarking UI into `reader.html` (EPUB) and `comic_reader.html`.
- [x] Task: Conductor - User Manual Verification 'Phase 2'
