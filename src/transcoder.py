import asyncio
import os
import logging
import subprocess
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

ENCODED_CACHE_DIR = Path("encoded_cache")
ENCODED_CACHE_DIR.mkdir(exist_ok=True)

async def transcode_video_task(
    video_id: int,
    file_path: str,
    output_filename: str,
    db_client,
    bot,
    user_id: int,
    title: str
):
    """
    백그라운드에서 영상을 모바일 호환(H.264/AAC MP4) 포맷으로 재인코딩합니다.
    """
    output_path = ENCODED_CACHE_DIR / output_filename
    temp_output_path = str(output_path) + ".tmp.mp4"
    
    logger.info(f"🔄 Starting transcoding for video {video_id}: {title}")
    
    try:
        # FFmpeg 명령: H.264(veryfast), AAC, FastStart 적용
        # -crf 23: 화질과 용량의 균형점
        # -vf "scale='min(1280,iw)':-2": 720p 수준으로 리사이징 (모바일 최적화 및 속도 향상)
        cmd = [
            "ffmpeg", "-y",
            "-i", file_path,
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "23",
            "-vf", "scale='min(1280,iw)':-2", 
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            temp_output_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            logger.error(f"❌ Transcoding failed: {stderr.decode()}")
            if os.path.exists(temp_output_path):
                os.remove(temp_output_path)
            return

        # 임시 파일을 최종 경로로 이동
        os.rename(temp_output_path, output_path)
        
        # DB 업데이트: 메타데이터에 인코딩 정보 저장
        try:
            # 기존 메타데이터 가져오기
            resp = await db_client.table("videos").select("metadata").eq("id", video_id).single().execute()
            metadata = resp.data.get("metadata") or {}
            
            metadata["encoded_path"] = str(output_path)
            metadata["is_encoded"] = True
            metadata["last_played"] = datetime.now().isoformat()
            
            await db_client.table("videos").update({"metadata": metadata}).eq("id", video_id).execute()
            logger.info(f"✅ Transcoding complete & DB updated: {title}")
            
            # 텔레그램 알림
            if bot and user_id:
                try:
                    await bot.send_message(
                        chat_id=user_id,
                        text=f"✅ **모바일 최적화(재인코딩) 완료!**\n\n📹 **{title}**\n\n이제 끊김 없이 재생할 수 있습니다! 🚀",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Failed to send telegram notification: {e}")
                    
        except Exception as db_e:
            logger.error(f"DB update failed after transcoding: {db_e}")

    except Exception as e:
        logger.error(f"Transcoding task error: {e}")
        if os.path.exists(temp_output_path):
            os.remove(temp_output_path)
    finally:
        # 원본 소스 파일이 임시 파일(다운로드된 파일)이라면 삭제 로직이 필요할 수 있음
        # 하지만 여기서는 원본 유지 정책에 따름 (bin channel에 있는건 유지)
        pass

async def cleanup_old_encoded_files(db_client):
    """
    일주일 이상 재생되지 않은 인코딩 파일을 삭제합니다.
    """
    logger.info("🧹 Starting cleanup of old encoded files...")
    expiry_date = datetime.now() - timedelta(days=7)
    
    try:
        # 인코딩된 비디오 조회
        # Note: Supabase JSON 필터링이 제한적일 수 있으므로 전체 인코딩된 항목을 가져와서 필터링
        # (실제 프로덕션에서는 더 효율적인 쿼리 필요)
        resp = await db_client.table("videos").select("id, metadata").execute()
        
        for video in resp.data:
            metadata = video.get("metadata") or {}
            if metadata.get("is_encoded"):
                last_played_str = metadata.get("last_played")
                if last_played_str:
                    last_played = datetime.fromisoformat(last_played_str)
                    
                    if last_played < expiry_date:
                        file_path = metadata.get("encoded_path")
                        if file_path and os.path.exists(file_path):
                            try:
                                os.remove(file_path)
                                logger.info(f"🗑️ Deleted expired encoded file: {file_path}")
                            except Exception as del_e:
                                logger.error(f"Failed to delete file {file_path}: {del_e}")
                        
                        # 메타데이터 업데이트 (인코딩 정보 제거)
                        del metadata["encoded_path"]
                        metadata["is_encoded"] = False
                        await db_client.table("videos").update({"metadata": metadata}).eq("id", video["id"]).execute()
                        
    except Exception as e:
        logger.error(f"Cleanup task failed: {e}")
