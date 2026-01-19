import zipfile
import re
import os
import logging
from pathlib import Path
from typing import Dict, Optional, Tuple, List
from PIL import Image
import io
from src.series_parser import extract_series_info

logger = logging.getLogger(__name__)

# 이미지 파일 확장자
IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.bmp'}


def is_comic_book(file_path: str) -> bool:
    """
    파일이 만화책(CBZ) 형식인지 판별

    Args:
        file_path: 파일 경로

    Returns:
        만화책이면 True, 아니면 False
    """
    try:
        # 1. 확장자 확인
        ext = Path(file_path).suffix.lower()
        if ext == '.cbz':
            return True

        # 2. ZIP 파일인 경우 내부 검사
        if ext == '.zip':
            if not zipfile.is_zipfile(file_path):
                return False

            with zipfile.ZipFile(file_path, 'r') as z:
                all_files = [f for f in z.namelist()
                           if not f.startswith('__MACOSX/')
                           and not f.startswith('.')
                           and not f.endswith('/')]

                if len(all_files) == 0:
                    return False

                # 이미지 파일 필터링
                image_files = [f for f in all_files
                             if Path(f).suffix.lower() in IMAGE_EXTENSIONS]

                # 이미지 비율이 80% 이상이면 만화책으로 판단
                image_ratio = len(image_files) / len(all_files)

                if image_ratio >= 0.8:
                    logger.info(f"Detected comic book: {file_path} "
                              f"(image ratio: {image_ratio:.2%})")
                    return True

        return False

    except Exception as e:
        logger.error(f"Error checking if comic book: {e}")
        return False


def get_page_count(file_path: str) -> int:
    """
    만화책의 총 페이지 수 반환

    Args:
        file_path: 만화책 파일 경로

    Returns:
        페이지 수 (이미지 파일 개수)
    """
    try:
        if not zipfile.is_zipfile(file_path):
            return 0

        with zipfile.ZipFile(file_path, 'r') as z:
            image_files = get_image_list(z)
            return len(image_files)

    except Exception as e:
        logger.error(f"Error getting page count: {e}")
        return 0


def get_image_list(zip_file: zipfile.ZipFile) -> List[str]:
    """
    ZIP 파일 내 이미지 파일 목록 반환 (정렬됨)

    Args:
        zip_file: ZipFile 객체

    Returns:
        정렬된 이미지 파일 경로 리스트
    """
    # 숨김 파일 및 메타데이터 폴더 제외
    all_files = [f for f in zip_file.namelist()
                if not f.startswith('__MACOSX/')
                and not f.startswith('.')
                and not f.endswith('/')]

    # 이미지 파일만 필터링
    image_files = [f for f in all_files
                  if Path(f).suffix.lower() in IMAGE_EXTENSIONS]

    # 자연스러운 정렬 (001, 002, ... 010, 011)
    def natural_sort_key(s):
        return [int(text) if text.isdigit() else text.lower()
                for text in re.split('([0-9]+)', s)]

    image_files.sort(key=natural_sort_key)

    return image_files


def extract_cover_image(file_path: str, max_size: int = 400) -> Tuple[Optional[bytes], str]:
    """
    만화책의 첫 페이지를 썸네일로 추출

    Args:
        file_path: 만화책 파일 경로
        max_size: 썸네일 최대 너비/높이 (px)

    Returns:
        (썸네일 바이너리, 확장자) 튜플
    """
    try:
        if not zipfile.is_zipfile(file_path):
            return None, ''

        with zipfile.ZipFile(file_path, 'r') as z:
            image_files = get_image_list(z)

            if len(image_files) == 0:
                logger.warning(f"No images found in {file_path}")
                return None, ''

            # 첫 번째 이미지 읽기
            first_image = image_files[0]
            image_bytes = z.read(first_image)

            # PIL로 이미지 열기
            img = Image.open(io.BytesIO(image_bytes))

            # 썸네일 크기 계산 (비율 유지)
            img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)

            # JPEG로 변환 (용량 절약)
            output = io.BytesIO()

            # RGBA → RGB 변환 (JPEG는 투명도 미지원)
            if img.mode in ('RGBA', 'LA', 'P'):
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = rgb_img

            img.save(output, format='JPEG', quality=85, optimize=True)
            thumbnail_bytes = output.getvalue()

            logger.info(f"Generated thumbnail: {len(thumbnail_bytes)} bytes "
                       f"({img.size[0]}x{img.size[1]})")

            return thumbnail_bytes, '.jpg'

    except Exception as e:
        logger.error(f"Error extracting cover image: {e}")
        return None, ''


def extract_comic_metadata(file_path: str, folder: str = None, original_filename: str = None) -> Dict:
    """
    만화책 파일에서 메타데이터 추출

    Args:
        file_path: 만화책 파일 경로
        folder: 폴더명 (선택)
        original_filename: 원본 파일명 (선택, 제공되지 않으면 file_path에서 추출)

    Returns:
        메타데이터 딕셔너리
    """
    metadata = {
        'title': None,
        'series': None,
        'volume': None,
        'page_count': 0,
        'cover_bytes': None,
        'cover_ext': None,
    }

    try:
        if not is_comic_book(file_path):
            logger.warning(f"Not a comic book: {file_path}")
            return metadata

        # 원본 파일명이 제공되면 사용, 아니면 file_path에서 추출
        filename = original_filename if original_filename else Path(file_path).name

        # 시리즈명, 권수 추출
        series, volume = extract_series_info(filename, folder)
        metadata['series'] = series
        metadata['volume'] = volume

        # 타이틀 = 시리즈명 + 권수
        if volume:
            metadata['title'] = f"{series} {volume}권"
        else:
            metadata['title'] = series

        # 페이지 수
        metadata['page_count'] = get_page_count(file_path)

        # 썸네일 추출
        cover_bytes, cover_ext = extract_cover_image(file_path)
        metadata['cover_bytes'] = cover_bytes
        metadata['cover_ext'] = cover_ext

        logger.info(f"Extracted metadata: {metadata['title']} "
                   f"({metadata['page_count']} pages)")

    except Exception as e:
        logger.error(f"Error extracting comic metadata: {e}")

    return metadata


def get_page_image(file_path: str, page_num: int) -> Tuple[Optional[bytes], str]:
    """
    만화책의 특정 페이지 이미지 반환

    Args:
        file_path: 만화책 파일 경로
        page_num: 페이지 번호 (0부터 시작)

    Returns:
        (이미지 바이너리, MIME 타입) 튜플
    """
    try:
        if not zipfile.is_zipfile(file_path):
            return None, ''

        with zipfile.ZipFile(file_path, 'r') as z:
            image_files = get_image_list(z)

            if page_num < 0 or page_num >= len(image_files):
                logger.warning(f"Page {page_num} out of range "
                             f"(0-{len(image_files)-1})")
                return None, ''

            image_path = image_files[page_num]
            image_bytes = z.read(image_path)

            # MIME 타입 결정
            ext = Path(image_path).suffix.lower()
            mime_types = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.webp': 'image/webp',
                '.gif': 'image/gif',
                '.bmp': 'image/bmp',
            }
            mime_type = mime_types.get(ext, 'image/jpeg')

            return image_bytes, mime_type

    except Exception as e:
        logger.error(f"Error getting page image: {e}")
        return None, ''
