-- Add views tracking table for analytics
CREATE TABLE IF NOT EXISTS views (
    id SERIAL PRIMARY KEY,
    short_id VARCHAR(8),
    user_id BIGINT,
    ip_address VARCHAR(45),
    user_agent TEXT,
    watched_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_views_short_id ON views(short_id);
CREATE INDEX IF NOT EXISTS idx_views_watched_at ON views(watched_at);
CREATE INDEX IF NOT EXISTS idx_views_user_id ON views(user_id);

-- Add views column to shared_links if not exists
ALTER TABLE shared_links 
ADD COLUMN IF NOT EXISTS views INTEGER DEFAULT 0;

-- Create index on views column in shared_links
CREATE INDEX IF NOT EXISTS idx_shared_links_views ON shared_links(views DESC);
