CREATE TABLE reading_progress (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    file_id BIGINT NOT NULL,
    cfi TEXT NOT NULL,
    percent REAL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, file_id)
);

CREATE INDEX idx_reading_progress_user ON reading_progress(user_id);

ALTER TABLE public.reading_progress ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Enable all for reading_progress" ON public.reading_progress FOR ALL USING (true) WITH CHECK (true);
