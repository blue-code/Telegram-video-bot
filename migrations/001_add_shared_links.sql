-- Create shared_links table for URL shortening
CREATE TABLE IF NOT EXISTS shared_links (
    id SERIAL PRIMARY KEY,
    short_id VARCHAR(8) UNIQUE NOT NULL,
    file_id TEXT NOT NULL,
    video_id INTEGER REFERENCES videos(id),
    user_id BIGINT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    views INTEGER DEFAULT 0
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_shared_links_short_id ON shared_links(short_id);
CREATE INDEX IF NOT EXISTS idx_shared_links_video_id ON shared_links(video_id);
