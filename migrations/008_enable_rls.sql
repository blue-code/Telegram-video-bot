-- 1. users 테이블
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Enable all for users" ON public.users FOR ALL USING (true) WITH CHECK (true);

-- 2. shared_links 테이블
ALTER TABLE public.shared_links ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Enable all for shared_links" ON public.shared_links FOR ALL USING (true) WITH CHECK (true);

-- 3. favorites 테이블
ALTER TABLE public.favorites ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Enable all for favorites" ON public.favorites FOR ALL USING (true) WITH CHECK (true);

-- 4. videos 테이블
ALTER TABLE public.videos ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Enable all for videos" ON public.videos FOR ALL USING (true) WITH CHECK (true);

-- 5. views 테이블
ALTER TABLE public.views ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Enable all for views" ON public.views FOR ALL USING (true) WITH CHECK (true);

-- 6. files 테이블
ALTER TABLE public.files ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Enable all for files" ON public.files FOR ALL USING (true) WITH CHECK (true);
