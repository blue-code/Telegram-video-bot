import logging
import re
import chardet
from pathlib import Path
from typing import List, Dict, Optional
from src import db

logger = logging.getLogger(__name__)

async def find_subtitle_files(video_file_name: str, user_id: int) -> List[Dict]:
    """
    Find subtitle files in DB that match the video file name.
    Matches video_name.srt, video_name.smi, video_name.lang.srt, etc.
    """
    # Remove extension from video name
    video_stem = Path(video_file_name).stem
    
    # Search for files with similar names
    # Note: get_files uses ilike %query%
    potential_files = await db.get_files(user_id=user_id, query=video_stem, limit=100)
    
    subtitle_files = []
    for f in potential_files:
        name = f.get("file_name", "")
        if name == video_file_name:
            continue
            
        # Check if it starts with video stem and is a subtitle extension
        if name.startswith(video_stem):
            ext = Path(name).suffix.lower()
            if ext in [".srt", ".smi"]:
                subtitle_files.append(f)
                
    return subtitle_files

def detect_encoding(content_bytes: bytes) -> str:
    """
    Detect encoding of the content using chardet.
    """
    result = chardet.detect(content_bytes)
    encoding = result.get('encoding', 'utf-8')
    if encoding is None:
        encoding = 'utf-8'
    return encoding

def convert_smi_to_vtt(smi_content: str) -> str:
    """
    Convert SAMI (.smi) subtitle content to WebVTT (.vtt).
    Basic implementation.
    """
    vtt_output = ["WEBVTT\n"]
    
    # Simple regex to extract sync points and text
    # <SYNC Start=1000><P Class=KRCC>Text...
    sync_pattern = re.compile(r'<SYNC\s+Start=(\d+)>', re.IGNORECASE)
    
    matches = list(sync_pattern.finditer(smi_content))
    
    def ms_to_vtt_time(ms: int) -> str:
        seconds = ms // 1000
        milliseconds = ms % 1000
        minutes = seconds // 60
        seconds = seconds % 60
        hours = minutes // 60
        minutes = minutes % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"

    for i in range(len(matches)):
        start_ms = int(matches[i].group(1))
        # End time is the next sync point, or start + 5s if last
        if i + 1 < len(matches):
            end_ms = int(matches[i+1].group(1))
        else:
            end_ms = start_ms + 5000
            
        # Extract text between sync points
        start_pos = matches[i].end()
        end_pos = matches[i+1].start() if i + 1 < len(matches) else len(smi_content)
        
        block_text = smi_content[start_pos:end_pos]
        
        # Strip HTML tags from text
        # <P Class=KRCC>Text -> Text
        text = re.sub(r'<[^>]+>', '', block_text).strip()
        
        # Replace &nbsp;
        text = text.replace('&nbsp;', '').strip()
        
        if text:
            vtt_output.append(f"{ms_to_vtt_time(start_ms)} --> {ms_to_vtt_time(end_ms)}")
            vtt_output.append(f"{text}\n")
            
    return "\n".join(vtt_output)

def convert_srt_to_vtt(srt_content: str) -> str:
    """
    Convert SRT subtitle content to WebVTT.
    SRT is almost identical to VTT except for the header and comma separator.
    """
    vtt_content = "WEBVTT\n\n" + srt_content
    # Replace comma in timestamps with dot (VTT requirement)
    # 00:00:01,000 -> 00:00:01.000
    vtt_content = re.sub(r'(\d{2}:\d{2}:\d{2}),(\d{3})', r'\1.\2', vtt_content)
    return vtt_content
