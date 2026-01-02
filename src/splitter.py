import asyncio
import os
import math
import subprocess

async def get_video_duration(file_path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    cmd = [
        "ffprobe", 
        "-v", "error", 
        "-show_entries", "format=duration", 
        "-of", "default=noprint_wrappers=1:nokey=1", 
        file_path
    ]
    
    import logging
    logging.info(f"Running ffprobe for: {file_path}")
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    stdout, stderr = await process.communicate()
    
    if process.returncode != 0:
        logging.error(f"ffprobe failed: {stderr.decode()}")
        raise Exception(f"ffprobe failed: {stderr.decode()}")
        
    duration = float(stdout.decode().strip())
    logging.info(f"ffprobe duration: {duration}")
    return duration

async def split_video(file_path: str, max_size_bytes: int = 2 * 1024 * 1024 * 1024) -> list[str]:
    """
    Splits video into chunks smaller than max_size_bytes.
    Returns list of file paths (including original if no split needed).
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
        
    current_size = os.path.getsize(file_path)
    
    if current_size <= max_size_bytes:
        return [file_path]
    
    # Calculate number of parts and duration per part
    duration = await get_video_duration(file_path)
    num_parts = math.ceil(current_size / max_size_bytes)
    part_duration = duration / num_parts
    
    output_parts = []
    base_name, ext = os.path.splitext(file_path)
    
    for i in range(num_parts):
        start_time = i * part_duration
        output_name = f"{base_name}_part{i+1}{ext}"
        
        # ffmpeg command to slice
        # -ss start_time -t part_duration -i input -c copy output
        # Using -c copy is fast but might not be perfectly accurate on keyframes.
        # For better accuracy but slower speed, remove "-c copy".
        # Let's use re-encoding for safety or try copy first? 
        # Plan says "FFmpeg 기반 영상 분할", let's use stream copy for speed first, 
        # but -ss before -i is faster.
        
        cmd = [
            "ffmpeg",
            "-y", # Overwrite
            "-ss", str(start_time),
            "-t", str(part_duration),
            "-i", file_path,
            "-c", "copy", # Stream copy for speed
            output_name
        ]
        
        import logging
        logging.info(f"Splitting part {i+1}/{num_parts}: {output_name}")
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logging.error(f"ffmpeg split failed: {stderr.decode()}")
            raise Exception(f"ffmpeg split failed: {stderr.decode()}")
            
        logging.info(f"Split part {i+1} completed.")
            
        output_parts.append(output_name)
        
    return output_parts
