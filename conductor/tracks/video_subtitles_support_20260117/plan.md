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

## Phase 2: Subtitle Streaming API [checkpoint: 9f3eaf1]
- [x] Task: Create API Endpoints
    - [x] Sub-task: Add `GET /api/subtitles/{file_id}` in `src/server.py` to stream converted VTT
    - [x] Sub-task: Handle file download from Telegram, conversion, and caching
- [x] Task: Update Video Watch Logic
    - [x] Sub-task: Modify `watch_video` route to fetch subtitle list for the video
    - [x] Sub-task: Pass subtitle tracks to `templates/watch.html` context
- [x] Task: Conductor - User Manual Verification 'Phase 2' (Protocol in workflow.md)

## Phase 3: Web Player Integration [checkpoint: 44d5271]
- [x] Task: Update Player UI
    - [x] Sub-task: Edit `templates/watch.html` to iterate over subtitle tracks and add `<track>` tags
    - [x] Sub-task: Ensure default subtitle selection logic (e.g., match browser language or first available)
- [x] Task: Conductor - User Manual Verification 'Phase 3' (Protocol in workflow.md)

## Phase 4: Transcoding Integration (Soft Subtitles) [checkpoint: b5a3c52]
- [x] Task: Update Transcoder
    - [x] Sub-task: Modify `src/transcoder.py` to check for subtitles before encoding
    - [x] Sub-task: Implement logic to download subtitle files to temp dir alongside video
    - [x] Sub-task: Update FFmpeg command to include subtitles: `-c:s mov_text` (map subtitle streams)
- [x] Task: Conductor - User Manual Verification 'Phase 4' (Protocol in workflow.md)
