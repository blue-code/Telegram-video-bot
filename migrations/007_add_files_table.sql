CREATE TABLE files (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    file_id TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_size BIGINT,
    mime_type TEXT,
    metadata JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_files_user_id ON files(user_id);
CREATE INDEX idx_files_name ON files(file_name);
