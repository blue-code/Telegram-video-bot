# Specification: Universal Series & Bookmarks

## Context
Users need a way to manually group related content (EPUBs and Comics) into series and track their reading progress/bookmarks more granularly than just "last read position".

## Goals
1.  **Manual Series Management**: Allow users to create custom series and add any content (EPUB/Comic) to them.
2.  **Advanced Bookmarking**: Allow creating named bookmarks with notes for any content.
3.  **Read Status**: Explicitly mark items as "Completed" or "Unread".

## Functional Requirements

### Series
-   **CRUD**: Create, Read, Update, Delete series.
-   **Ordering**: Manually reorder items within a series.
-   **Mixed Content**: (Future) Support mixing EPUB and Comics in one series (currently segregated by type in API).
-   **Metadata**: Title, Description, Cover Image.

### Bookmarks
-   **CRUD**: Create, Read, Update, Delete bookmarks.
-   **Data**: Page/CFI, % progress, Title, Note.

### Completion
-   **Toggle**: Mark as read/unread.
-   **Visuals**: Visual indicator for completed items.

## Technical Architecture
-   **Database**: New tables `series`, `series_items`, `bookmarks`, `read_progress` (or similar).
-   **API**: `src/api_bookmarks_series.py` handling all logic.
-   **Frontend**: `static/bookmarks-series.js` for UI interactions.
