"""
기존 업로드된 ZIP 파일을 만화책으로 마이그레이션하는 스크립트

사용법:
    python migrate_existing_comics.py
"""

import asyncio
import os
import sys
import logging
import base64
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.db import get_database, get_files, save_comic_metadata
from src.comic_parser import is_comic_book, extract_comic_metadata

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def migrate_comics():
    """기존 ZIP/CBZ 파일을 만화책으로 마이그레이션"""

    logger.info("=" * 60)
    logger.info("만화책 마이그레이션 시작")
    logger.info("=" * 60)

    try:
        # Supabase 연결
        sb = await get_database()
        logger.info("✓ 데이터베이스 연결 성공")

        # 모든 파일 가져오기 (대량 처리)
        offset = 0
        limit = 100
        total_files = 0
        total_comics = 0
        total_skipped = 0

        while True:
            # 파일 목록 가져오기 (모든 사용자)
            result = await sb.table("files").select("*").order("created_at", desc=False).range(offset, offset + limit - 1).execute()

            if not result.data:
                break

            files = result.data
            logger.info(f"\n📦 {offset + 1}~{offset + len(files)} 파일 처리 중...")

            for file_data in files:
                total_files += 1

                file_id = file_data.get("id")
                file_name = file_data.get("file_name", "")
                file_path = file_data.get("file_path")
                user_id = file_data.get("user_id")

                # ZIP 또는 CBZ 파일만 처리
                if not file_name.lower().endswith(('.zip', '.cbz')):
                    continue

                # 파일 경로 확인
                if not file_path or not os.path.exists(file_path):
                    logger.warning(f"  ⚠️  파일 없음: {file_name}")
                    total_skipped += 1
                    continue

                # 이미 comics 테이블에 있는지 확인
                existing = await sb.table("comics").select("id").eq("file_id", file_id).execute()
                if existing.data:
                    logger.debug(f"  ⏭️  이미 등록됨: {file_name}")
                    total_skipped += 1
                    continue

                # 만화책인지 확인
                try:
                    is_comic = await asyncio.to_thread(is_comic_book, file_path)

                    if not is_comic:
                        logger.debug(f"  ❌ 만화책 아님: {file_name}")
                        total_skipped += 1
                        continue

                    # 메타데이터 추출 (원본 파일명 전달)
                    comic_meta = await asyncio.to_thread(
                        extract_comic_metadata,
                        file_path,
                        None,  # folder
                        file_name  # original_filename
                    )

                    # Convert thumbnail bytes to base64 for JSON serialization
                    cover_bytes = comic_meta.get("cover_bytes")
                    cover_base64 = base64.b64encode(cover_bytes).decode('utf-8') if cover_bytes else None

                    # DB에 저장
                    comic_db_data = {
                        "file_id": file_id,
                        "user_id": user_id,
                        "title": comic_meta.get("title") or file_name,
                        "series": comic_meta.get("series"),
                        "volume": comic_meta.get("volume"),
                        "folder": comic_meta.get("folder"),
                        "page_count": comic_meta.get("page_count", 0),
                        "metadata": {
                            "cover_base64": cover_base64,
                            "cover_ext": comic_meta.get("cover_ext")
                        }
                    }

                    await save_comic_metadata(comic_db_data)

                    total_comics += 1
                    logger.info(f"  ✅ 등록 완료: {comic_meta.get('title')} (시리즈: {comic_meta.get('series')}, {comic_meta.get('page_count')}p)")

                except Exception as e:
                    logger.error(f"  ❌ 오류 발생: {file_name} - {e}")
                    total_skipped += 1
                    continue

            # 다음 배치로 이동
            offset += limit

            # 진행 상황 출력
            logger.info(f"진행 상황: 총 {total_files}개 파일 검사, {total_comics}개 만화책 등록, {total_skipped}개 스킵")

        # 최종 결과
        logger.info("\n" + "=" * 60)
        logger.info("마이그레이션 완료!")
        logger.info("=" * 60)
        logger.info(f"📊 총 검사 파일: {total_files}개")
        logger.info(f"✅ 등록된 만화책: {total_comics}개")
        logger.info(f"⏭️  스킵된 파일: {total_skipped}개")
        logger.info("=" * 60)

        if total_comics > 0:
            logger.info("\n🎉 만화책 라이브러리에서 확인하세요!")
            logger.info("   http://localhost:8000/comics/{user_id}")

    except Exception as e:
        logger.error(f"마이그레이션 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("📚 만화책 마이그레이션 도구")
    print("=" * 60)
    print("기존 업로드된 ZIP/CBZ 파일을 만화책으로 등록합니다.\n")

    response = input("계속하시겠습니까? (y/n): ")

    if response.lower() != 'y':
        print("취소되었습니다.")
        sys.exit(0)

    print()
    asyncio.run(migrate_comics())
