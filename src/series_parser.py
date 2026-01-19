import re
import logging
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# 시리즈명 추출 패턴 (우선순위 순)
SERIES_PATTERNS = [
    # "제목 - 01화" (하이픈 포함 패턴을 먼저 검사)
    r'^(.+?)\s*-\s*(\d+)화\s*$',

    # "제목 9화", "그거 그렇게 하는거 아닌데 9화"
    r'^(.+?)\s*(\d+)화\s*$',

    # "[작가명] 제목 01" -> "제목", 1
    r'^\[.+?\]\s*(.+?)\s*(\d+)\s*$',

    # "제목 (01)"
    r'^(.+?)\s*\((\d+)\)\s*$',

    # "원피스 1권", "원피스 100권"
    r'^(.+?)\s+(\d+)권\s*$',

    # "OnePiece vol.1", "OnePiece vol 001"
    r'^(.+?)\s+vol\.?\s*(\d+)\s*$',

    # "Naruto ch.001", "Naruto ch 1"
    r'^(.+?)\s+ch\.?\s*(\d+)\s*$',

    # "Bleach_01", "Bleach-001"
    r'^(.+?)[_-](\d+)\s*$',

    # "원피스01", "원피스001" (공백 없이 바로 숫자)
    r'^(.+?)(\d{2,})\s*$',
]

def extract_series_info(filename: str, folder: str = None) -> Tuple[Optional[str], Optional[int]]:
    """
    파일명과 폴더명에서 시리즈명과 권수 추출

    Args:
        filename: 파일명 (확장자 포함 가능)
        folder: 폴더명 (선택)

    Returns:
        (시리즈명, 권수) 튜플
    """
    # 확장자 제거
    name = Path(filename).stem

    # 각 패턴 시도
    for pattern in SERIES_PATTERNS:
        match = re.match(pattern, name, re.IGNORECASE)
        if match:
            series_name = match.group(1).strip()
            volume_str = match.group(2)
            try:
                volume = int(volume_str)
                logger.info(f"Extracted series: '{series_name}' vol.{volume} from '{filename}'")
                return series_name, volume
            except ValueError:
                continue

    # 패턴 매칭 실패 시 폴더명을 시리즈명으로 사용
    if folder:
        logger.info(f"Using folder name as series: '{folder}'")
        return folder, None

    # 폴더명도 없으면 파일명 전체를 시리즈명으로 사용
    logger.info(f"Using filename as series: '{name}'")
    return name, None
