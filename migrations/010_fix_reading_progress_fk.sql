-- 1. Foreign Key 추가
ALTER TABLE reading_progress
ADD CONSTRAINT fk_reading_progress_files
FOREIGN KEY (file_id)
REFERENCES files (id)
ON DELETE CASCADE;

-- 2. RLS 활성화 및 정책 추가
ALTER TABLE reading_progress ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Enable all for reading_progress" ON reading_progress FOR ALL USING (true) WITH CHECK (true);
