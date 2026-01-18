import pytest
from unittest.mock import patch, AsyncMock
from src.subtitle_manager import find_subtitle_files, detect_encoding, convert_smi_to_vtt

@pytest.mark.asyncio
async def test_find_subtitle_files():
    video_name = "test_movie.mp4"
    user_id = 123
    
    mock_files = [
        {"id": 1, "file_name": "test_movie.srt"},
        {"id": 2, "file_name": "test_movie.en.srt"},
        {"id": 3, "file_name": "other.srt"}
    ]
    
    with patch("src.db.get_files", new_callable=AsyncMock) as mock_get_files:
        mock_get_files.return_value = mock_files
        
        results = await find_subtitle_files(video_name, user_id)
        
        assert len(results) == 2
        assert results[0]["file_name"] == "test_movie.srt"
        assert results[1]["file_name"] == "test_movie.en.srt"

def test_detect_encoding():
    # UTF-8 content
    content = "안녕하세요".encode("utf-8")
    assert detect_encoding(content) == "utf-8"
    
    # EUC-KR content
    content_euc = "안녕하세요".encode("euc-kr")
    assert detect_encoding(content_euc).lower() in ["euc-kr", "cp949"]

def test_convert_smi_to_vtt():
    smi_content = """
    <SAMI>
    <BODY>
    <SYNC Start=1000><P Class=KRCC>
    Hello World!
    <SYNC Start=2000><P Class=KRCC>
    &nbsp;
    </BODY>
    </SAMI>
    """
    vtt = convert_smi_to_vtt(smi_content)
    assert "WEBVTT" in vtt
    assert "00:00:01.000 --> 00:00:02.000" in vtt
    assert "Hello World!" in vtt
