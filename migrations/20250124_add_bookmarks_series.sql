-- Migration: Add bookmarks, series, and read status tracking
-- Date: 2025-01-24
-- Description: Add bookmark functionality, series management, and read completion tracking for EPUB and Comics

-- ============================================================
-- 1. Add read completion tracking to files table (for EPUB)
-- ============================================================
ALTER TABLE files
ADD COLUMN IF NOT EXISTS is_completed BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP WITH TIME ZONE;

COMMENT ON COLUMN files.is_completed IS 'Whether user has finished reading this file (EPUB)';
COMMENT ON COLUMN files.completed_at IS 'Timestamp when file was marked as completed';

-- ============================================================
-- 2. Add read completion tracking to comics table
-- ============================================================
ALTER TABLE comics
ADD COLUMN IF NOT EXISTS is_completed BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP WITH TIME ZONE;

COMMENT ON COLUMN comics.is_completed IS 'Whether user has finished reading this comic';
COMMENT ON COLUMN comics.completed_at IS 'Timestamp when comic was marked as completed';

-- ============================================================
-- 3. Create bookmarks table (for both EPUB and Comics)
-- ============================================================
CREATE TABLE IF NOT EXISTS bookmarks (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    file_id TEXT NOT NULL,
    content_type TEXT NOT NULL CHECK (content_type IN ('epub', 'comic')),

    -- For EPUB: CFI, percentage
    -- For Comic: page number
    bookmark_position JSONB NOT NULL,

    -- User-defined bookmark name
    title TEXT NOT NULL,

    -- Optional note
    note TEXT,

    -- Thumbnail (base64 for small images or file_id for larger)
    thumbnail TEXT,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for fast lookup
CREATE INDEX IF NOT EXISTS idx_bookmarks_user_file ON bookmarks(user_id, file_id);
CREATE INDEX IF NOT EXISTS idx_bookmarks_user_type ON bookmarks(user_id, content_type);
CREATE INDEX IF NOT EXISTS idx_bookmarks_created ON bookmarks(created_at DESC);

COMMENT ON TABLE bookmarks IS 'User bookmarks for specific pages/positions in books and comics';
COMMENT ON COLUMN bookmarks.bookmark_position IS 'JSONB: {cfi, percentage, page} depending on content type';

-- ============================================================
-- 4. Create series table
-- ============================================================
CREATE TABLE IF NOT EXISTS series (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    content_type TEXT NOT NULL CHECK (content_type IN ('epub', 'comic', 'mixed')),

    -- Cover image (optional)
    cover_image TEXT,

    -- Metadata
    metadata JSONB DEFAULT '{}',

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_series_user ON series(user_id);
CREATE INDEX IF NOT EXISTS idx_series_type ON series(content_type);

COMMENT ON TABLE series IS 'User-created series/collections of books or comics';

-- ============================================================
-- 5. Create series_items table (junction table)
-- ============================================================
CREATE TABLE IF NOT EXISTS series_items (
    id BIGSERIAL PRIMARY KEY,
    series_id BIGINT NOT NULL REFERENCES series(id) ON DELETE CASCADE,
    file_id TEXT NOT NULL,
    content_type TEXT NOT NULL CHECK (content_type IN ('epub', 'comic')),

    -- Order within series (1, 2, 3, ...)
    item_order INTEGER NOT NULL DEFAULT 1,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Ensure unique items in series
    UNIQUE(series_id, file_id)
);

CREATE INDEX IF NOT EXISTS idx_series_items_series ON series_items(series_id);
CREATE INDEX IF NOT EXISTS idx_series_items_file ON series_items(file_id);
CREATE INDEX IF NOT EXISTS idx_series_items_order ON series_items(series_id, item_order);

COMMENT ON TABLE series_items IS 'Items (books/comics) belonging to a series';

-- ============================================================
-- 6. Create view for series with progress
-- ============================================================
CREATE OR REPLACE VIEW series_with_progress AS
SELECT
    s.id,
    s.user_id,
    s.title,
    s.description,
    s.content_type,
    s.cover_image,
    s.metadata,
    s.created_at,
    s.updated_at,
    COUNT(DISTINCT si.file_id) as total_items,
    COUNT(DISTINCT CASE
        WHEN si.content_type = 'epub' AND f.is_completed = TRUE THEN si.file_id
        WHEN si.content_type = 'comic' AND c.is_completed = TRUE THEN si.file_id
    END) as completed_items
FROM series s
LEFT JOIN series_items si ON s.id = si.series_id
LEFT JOIN files f ON si.file_id = CAST(f.file_id AS TEXT) AND si.content_type = 'epub' AND f.user_id = s.user_id
LEFT JOIN comics c ON si.file_id = CAST(c.file_id AS TEXT) AND si.content_type = 'comic' AND c.user_id = s.user_id
GROUP BY s.id, s.user_id, s.title, s.description, s.content_type, s.cover_image, s.metadata, s.created_at, s.updated_at;

COMMENT ON VIEW series_with_progress IS 'Series with completion progress statistics';

-- ============================================================
-- 7. Create function to auto-update updated_at (if not exists)
-- ============================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to relevant tables
DROP TRIGGER IF EXISTS update_bookmarks_updated_at ON bookmarks;
CREATE TRIGGER update_bookmarks_updated_at
    BEFORE UPDATE ON bookmarks
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_series_updated_at ON series;
CREATE TRIGGER update_series_updated_at
    BEFORE UPDATE ON series
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================
-- 8. Grant permissions (adjust as needed for your setup)
-- ============================================================
GRANT ALL ON bookmarks TO postgres, anon, authenticated, service_role;
GRANT ALL ON series TO postgres, anon, authenticated, service_role;
GRANT ALL ON series_items TO postgres, anon, authenticated, service_role;
GRANT USAGE, SELECT ON SEQUENCE bookmarks_id_seq TO postgres, anon, authenticated, service_role;
GRANT USAGE, SELECT ON SEQUENCE series_id_seq TO postgres, anon, authenticated, service_role;
GRANT USAGE, SELECT ON SEQUENCE series_items_id_seq TO postgres, anon, authenticated, service_role;
