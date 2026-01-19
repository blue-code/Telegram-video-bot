# Implementation Plan - EPUB Series Grouping & Rescan

## Phase 1: Logic & Database Updates [checkpoint: pending]
- [x] Task: Create `src/epub_migration.py`
    - [x] Sub-task: Implement `migrate_epub_series(user_id)` function (similar to comic migration but for .epub).
    - [x] Sub-task: Reuse regex patterns from `src/comic_parser.py` (extract to shared util if needed) to parse EPUB filenames.
    - [x] Sub-task: Update `files.metadata` JSONB with `series` and `volume` fields. (Unlike comics table, EPUBs usually live in `files` table with metadata).
- [x] Task: Create Rescan API Endpoint
    - [x] Sub-task: Add `POST /api/epub/migrate` in `src/server.py`.
- [x] Task: Conductor - User Manual Verification 'Phase 1' (Protocol in workflow.md)

## Phase 2: eBook Library UI Updates [checkpoint: 0481091]
- [x] Task: Create Series List Template (`templates/books_series.html`)
    - [x] Sub-task: Create a new template or modify `templates/books.html` to display series cards.
    - [x] Sub-task: Implement logic to group books by `metadata->series` in the template or backend query.
- [x] Task: Create Series Detail Template (`templates/book_series_detail.html`)
    - [x] Sub-task: Display list of books belonging to a specific series.
- [x] Task: Update `src/server.py` Routes
    - [x] Sub-task: Modify `/books/{user_id}` to render the grouped series view.
    - [x] Sub-task: Add `/books/series/{user_id}/{series_name}` route.
- [x] Task: Add Rescan Button
    - [x] Sub-task: Add "🔄 시리즈 재정리" button to the eBook library header.
    - [x] Sub-task: Connect button to the migration API.
- [x] Task: Conductor - User Manual Verification 'Phase 2' (Protocol in workflow.md)
