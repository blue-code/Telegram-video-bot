-- Add user_id column to videos table for multi-user support
ALTER TABLE videos ADD COLUMN IF NOT EXISTS user_id BIGINT;

-- Create index for faster user queries
CREATE INDEX IF NOT EXISTS idx_videos_user_id ON videos(user_id);
