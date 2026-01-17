-- ============================================
-- 만화책 기능을 위한 Supabase 테이블 생성 스크립트
-- ============================================
-- 사용 방법:
-- 1. Supabase 대시보드 > SQL Editor 열기
-- 2. 아래 SQL 전체 복사하여 붙여넣기
-- 3. RUN 버튼 클릭
-- ============================================

-- 1. comics 테이블: 만화책 메타데이터 저장
CREATE TABLE IF NOT EXISTS comics (
    id SERIAL PRIMARY KEY,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    series TEXT,
    volume INTEGER,
    folder TEXT,
    page_count INTEGER DEFAULT 0,
    cover_url TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Indexes
    CONSTRAINT comics_file_id_unique UNIQUE (file_id)
);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_comics_user_id ON comics(user_id);
CREATE INDEX IF NOT EXISTS idx_comics_series ON comics(series);
CREATE INDEX IF NOT EXISTS idx_comics_file_id ON comics(file_id);
CREATE INDEX IF NOT EXISTS idx_comics_created_at ON comics(created_at DESC);

-- 2. comic_progress 테이블: 읽기 진행 상태 저장
CREATE TABLE IF NOT EXISTS comic_progress (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    current_page INTEGER DEFAULT 0,
    settings JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Prevent duplicate progress entries per user+file
    CONSTRAINT comic_progress_user_file_unique UNIQUE (user_id, file_id)
);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_comic_progress_user_id ON comic_progress(user_id);
CREATE INDEX IF NOT EXISTS idx_comic_progress_file_id ON comic_progress(file_id);
CREATE INDEX IF NOT EXISTS idx_comic_progress_updated_at ON comic_progress(updated_at DESC);

-- 3. comic_favorites 테이블: 즐겨찾기
CREATE TABLE IF NOT EXISTS comic_favorites (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    file_id INTEGER NOT NULL REFERENCES files(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Prevent duplicate favorites
    CONSTRAINT comic_favorites_user_file_unique UNIQUE (user_id, file_id)
);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_comic_favorites_user_id ON comic_favorites(user_id);
CREATE INDEX IF NOT EXISTS idx_comic_favorites_file_id ON comic_favorites(file_id);
CREATE INDEX IF NOT EXISTS idx_comic_favorites_created_at ON comic_favorites(created_at DESC);

-- 4. Enable Row Level Security (RLS) for privacy
ALTER TABLE comics ENABLE ROW LEVEL SECURITY;
ALTER TABLE comic_progress ENABLE ROW LEVEL SECURITY;
ALTER TABLE comic_favorites ENABLE ROW LEVEL SECURITY;

-- 4. RLS Policies
-- Allow users to view their own comics
CREATE POLICY "Users can view own comics"
    ON comics FOR SELECT
    USING (auth.uid()::text = user_id::text OR user_id = 41509535);

-- Allow users to insert their own comics
CREATE POLICY "Users can insert own comics"
    ON comics FOR INSERT
    WITH CHECK (auth.uid()::text = user_id::text OR user_id = 41509535);

-- Allow users to update their own comics
CREATE POLICY "Users can update own comics"
    ON comics FOR UPDATE
    USING (auth.uid()::text = user_id::text OR user_id = 41509535);

-- Allow users to delete their own comics
CREATE POLICY "Users can delete own comics"
    ON comics FOR DELETE
    USING (auth.uid()::text = user_id::text OR user_id = 41509535);

-- Comic progress policies
CREATE POLICY "Users can view own comic progress"
    ON comic_progress FOR SELECT
    USING (auth.uid()::text = user_id::text OR user_id = 41509535);

CREATE POLICY "Users can insert own comic progress"
    ON comic_progress FOR INSERT
    WITH CHECK (auth.uid()::text = user_id::text OR user_id = 41509535);

CREATE POLICY "Users can update own comic progress"
    ON comic_progress FOR UPDATE
    USING (auth.uid()::text = user_id::text OR user_id = 41509535);

CREATE POLICY "Users can delete own comic progress"
    ON comic_progress FOR DELETE
    USING (auth.uid()::text = user_id::text OR user_id = 41509535);

-- Comic favorites policies
CREATE POLICY "Users can view own comic favorites"
    ON comic_favorites FOR SELECT
    USING (auth.uid()::text = user_id::text OR user_id = 41509535);

CREATE POLICY "Users can insert own comic favorites"
    ON comic_favorites FOR INSERT
    WITH CHECK (auth.uid()::text = user_id::text OR user_id = 41509535);

CREATE POLICY "Users can delete own comic favorites"
    ON comic_favorites FOR DELETE
    USING (auth.uid()::text = user_id::text OR user_id = 41509535);

-- 5. Trigger to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to comics table
DROP TRIGGER IF EXISTS update_comics_updated_at ON comics;
CREATE TRIGGER update_comics_updated_at
    BEFORE UPDATE ON comics
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Apply trigger to comic_progress table
DROP TRIGGER IF EXISTS update_comic_progress_updated_at ON comic_progress;
CREATE TRIGGER update_comic_progress_updated_at
    BEFORE UPDATE ON comic_progress
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 6. Grant necessary permissions (if using service role)
-- This ensures the FastAPI backend can access the tables
GRANT ALL ON comics TO postgres, anon, authenticated, service_role;
GRANT ALL ON comic_progress TO postgres, anon, authenticated, service_role;
GRANT ALL ON comic_favorites TO postgres, anon, authenticated, service_role;
GRANT USAGE, SELECT ON SEQUENCE comics_id_seq TO postgres, anon, authenticated, service_role;
GRANT USAGE, SELECT ON SEQUENCE comic_progress_id_seq TO postgres, anon, authenticated, service_role;
GRANT USAGE, SELECT ON SEQUENCE comic_favorites_id_seq TO postgres, anon, authenticated, service_role;

-- ============================================
-- 완료! 테이블 생성 성공
-- ============================================
-- 확인 방법:
-- SELECT * FROM comics LIMIT 10;
-- SELECT * FROM comic_progress LIMIT 10;
-- ============================================
