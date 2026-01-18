# Implementation Plan - Video Subtitles Support

## Phase 1: Subtitle Logic Implementation [checkpoint: 2e128c0]
- [x] Task: Add Dependencies
    - [x] Sub-task: Add `chardet` to `requirements.txt` for encoding detection
- [x] Task: Create Subtitle Manager Module (`src/subtitle_manager.py`)
    - [x] Sub-task: Implement `find_subtitle_files(video_file_name, user_id)` to search DB for matching subtitles
    - [x] Sub-task: Implement `detect_encoding(file_path)` using chardet
    - [x] Sub-task: Implement `convert_smi_to_vtt(smi_content)` parser
    - [x] Sub-task: Implement `convert_srt_to_vtt(srt_content)` (if needed, mainly for cleanup)
- [x] Task: Conductor - User Manual Verification 'Phase 1' (Protocol in workflow.md)

## Phase 2: Subtitle Streaming API
- [ ] Task: Create API Endpoints
    - [ ] Sub-task: Add `GET /api/subtitles/{file_id}` in `src/server.py` to stream converted VTT
    - [ ] Sub-task: Handle file download from Telegram, conversion, and caching
- [ ] Task: Update Video Watch Logic
    - [ ] Sub-task: Modify `watch_video` route to fetch subtitle list for the video
    - [ ] Sub-task: Pass subtitle tracks to `templates/watch.html` context
- [ ] Task: Conductor - User Manual Verification 'Phase 2' (Protocol in workflow.md)

## Phase 3: Web Player Integration
- [ ] Task: Update Player UI
    - [ ] Sub-task: Edit `templates/watch.html` to iterate over subtitle tracks and add `<track>` tags
    - [ ] Sub-task: Ensure default subtitle selection logic (e.g., match browser language or first available)
- [ ] Task: Conductor - User Manual Verification 'Phase 3' (Protocol in workflow.md)

## Phase 4: Transcoding Integration (Soft Subtitles)
- [ ] Task: Update Transcoder
    - [ ] Sub-task: Modify `src/transcoder.py` to check for subtitles before encoding
    - [ ] Sub-task: Implement logic to download subtitle files to temp dir alongside video
    - [ ] Sub-task: Update FFmpeg command to include subtitles: `-c:s mov_text` (map subtitle streams)
- [ ] Task: Conductor - User Manual Verification 'Phase 4' (Protocol in workflow.md)
