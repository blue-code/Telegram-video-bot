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
