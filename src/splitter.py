import asyncio
import json
import math
import os
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
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        returncode = process.returncode
    except NotImplementedError:
        result = await asyncio.to_thread(
            subprocess.run,
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout = result.stdout
        stderr = result.stderr
        returncode = result.returncode
    
    if returncode != 0:
        error_msg = stderr.decode(errors="replace")
        logging.error(f"ffprobe failed: {error_msg}")
        raise Exception(f"ffprobe failed: {error_msg}")
        
    duration = float(stdout.decode().strip())
    logging.info(f"ffprobe duration: {duration}")
    return duration

async def get_video_stream_metadata(file_path: str) -> dict:
    """Get video stream metadata needed to preserve aspect ratio."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=sample_aspect_ratio,display_aspect_ratio:stream_tags=rotate",
        "-of", "json",
        file_path
    ]

    import logging
    logging.info(f"Running ffprobe (metadata) for: {file_path}")
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        returncode = process.returncode
    except NotImplementedError:
        result = await asyncio.to_thread(
            subprocess.run,
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        stdout = result.stdout
        stderr = result.stderr
        returncode = result.returncode

    if returncode != 0:
        error_msg = stderr.decode(errors="replace")
        logging.error(f"ffprobe metadata failed: {error_msg}")
        return {}

    try:
        data = json.loads(stdout.decode(errors="replace") or "{}")
    except json.JSONDecodeError:
        logging.warning("ffprobe metadata returned invalid JSON.")
        return {}

    streams = data.get("streams") or []
    if not streams:
        return {}

    stream = streams[0] or {}
    tags = stream.get("tags") or {}
    return {
        "sample_aspect_ratio": stream.get("sample_aspect_ratio"),
        "display_aspect_ratio": stream.get("display_aspect_ratio"),
        "rotate": tags.get("rotate")
    }

async def split_video(
    file_path: str,
    max_size_bytes: int = 2 * 1024 * 1024 * 1024,
    transcode: bool = False
) -> list[str]:
    """
    Splits video into chunks smaller than max_size_bytes.
    Returns list of file paths (including original if no split needed).
    If transcode=True, re-encode while preserving display aspect ratio metadata.
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
    stream_meta = {}
    if transcode:
        stream_meta = await get_video_stream_metadata(file_path)
    
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
            "-i", file_path
        ]

        if transcode:
            scale_filter = "scale=trunc(iw/2)*2:trunc(ih/2)*2"
            sar = (stream_meta.get("sample_aspect_ratio") or "").strip()
            dar = (stream_meta.get("display_aspect_ratio") or "").strip()
            rotate = stream_meta.get("rotate")

            if sar and sar not in ("1:1", "1", "0:1", "N/A"):
                scale_filter = (
                    "scale=trunc(iw*sar/2)*2:trunc(ih/2)*2,setsar=1"
                )

            cmd += [
                "-vf", scale_filter,
                "-c:v", "libx264",
                "-crf", "18",
                "-preset", "veryfast",
                "-pix_fmt", "yuv420p",
                "-c:a", "aac",
                "-b:a", "192k",
                "-movflags", "+faststart"
            ]
            if dar and dar not in ("0:1", "N/A"):
                cmd += ["-aspect", dar]
            if rotate:
                cmd += ["-metadata:s:v:0", f"rotate={rotate}"]
        else:
            cmd += [
                "-c", "copy" # Stream copy for speed
            ]

        cmd.append(output_name)
        
        import logging
        logging.info(f"Splitting part {i+1}/{num_parts}: {output_name}")
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            returncode = process.returncode
        except NotImplementedError:
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            stdout = result.stdout
            stderr = result.stderr
            returncode = result.returncode
        
        if returncode != 0:
            error_msg = stderr.decode(errors="replace")
            logging.error(f"ffmpeg split failed: {error_msg}")
            raise Exception(f"ffmpeg split failed: {error_msg}")
            
        logging.info(f"Split part {i+1} completed.")
            
        output_parts.append(output_name)
        
    final_parts = []
    for part_path in output_parts:
        try:
            part_size = os.path.getsize(part_path)
        except OSError:
            final_parts.append(part_path)
            continue

        if part_size <= max_size_bytes:
            final_parts.append(part_path)
            continue

        # If a part still exceeds size, split again without re-encoding.
        sub_parts = await split_video(part_path, max_size_bytes, transcode=False)
        if sub_parts != [part_path] and os.path.exists(part_path):
            try:
                os.remove(part_path)
            except OSError:
                pass
        final_parts.extend(sub_parts)

    return final_parts
