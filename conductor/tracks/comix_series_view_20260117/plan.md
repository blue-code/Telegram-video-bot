# Implementation Plan - Comic Series View & Dashboard Integration

## Phase 1: Logic Updates & Migration Tooling [checkpoint: 2476b6f]
- [x] Task: Update `src/comic_parser.py` with new regex patterns for series detection
    - [x] Sub-task: Add pattern `^(.+?)\s*(\d+)화` ("제목 9화")
    - [x] Sub-task: Add pattern `^(.+?)\s*-\s*(\d+)화` ("제목 - 01화")
    - [x] Sub-task: Add pattern `^\[.+?\]\s*(.+?)\s*(\d+)` ("[작가] 제목 01")
    - [x] Sub-task: Add pattern `^(.+?)\s*\((\d+)\)` ("제목 (01)")
    - [x] Sub-task: Verify regex patterns with test cases
- [x] Task: Create migration logic
    - [x] Sub-task: Implement `migrate_comic_series()` in `src/comic_parser.py` or `src/file_manager.py` to rescan all files in DB
    - [x] Sub-task: Create standalone script `migrations/run_comic_migration.py`
    - [x] Sub-task: Add startup check in `src/server.py` to run migration (configurable via env var or always-on mostly-harmless check)
- [x] Task: Conductor - User Manual Verification 'Phase 1' (Protocol in workflow.md)

## Phase 2: Dashboard "Continue Reading" Integration
- [ ] Task: Backend - Update Dashboard Endpoint
    - [ ] Sub-task: Modify `dashboard` route in `src/server.py` to fetch recent comic reading progress via `db.get_recent_comic_reading`
- [ ] Task: Frontend - Update Dashboard UI
    - [ ] Sub-task: Edit `templates/dashboard.html` to add "Continue Reading" section
    - [ ] Sub-task: Display cover image, series/title, and "Continue" button linking to the last read page
- [ ] Task: Conductor - User Manual Verification 'Phase 2' (Protocol in workflow.md)

## Phase 3: Comics Menu Reorganization
- [ ] Task: Update Web Routing for Comics
    - [ ] Sub-task: Modify `/comics/{user_id}` in `src/server.py` to render the Series View by default
    - [ ] Sub-task: Create new route `/comics/files/{user_id}` for the old flat file list
- [ ] Task: Update Templates
    - [ ] Sub-task: Update `templates/comic_series_list.html` to act as the main landing page (add tabs/links to "All Files")
    - [ ] Sub-task: Update `templates/comics.html` (or rename to `comic_files.html`) to include a "Back to Series" tab/link
    - [ ] Sub-task: Ensure Navigation Bar links point to the correct default view
- [ ] Task: Conductor - User Manual Verification 'Phase 3' (Protocol in workflow.md)

## Phase 4: Migration UI & Admin Controls
- [ ] Task: Add Migration Trigger to UI
    - [ ] Sub-task: Add "Rescan Comics" button in Admin/Files area (e.g., `templates/files.html` or a new settings modal)
    - [ ] Sub-task: Implement API endpoint to trigger migration from UI
- [ ] Task: Final Verification
    - [ ] Sub-task: Verify legacy file migration
    - [ ] Sub-task: Verify new file uploads are correctly categorized
    - [ ] Sub-task: Check mobile responsiveness of new views
- [ ] Task: Conductor - User Manual Verification 'Phase 4' (Protocol in workflow.md)
