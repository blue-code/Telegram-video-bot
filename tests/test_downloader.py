import pytest
from unittest.mock import patch, MagicMock
from src.downloader import extract_video_info

@pytest.mark.asyncio
async def test_extract_video_info_success():
    mock_info = {
        'id': 'video123',
        'title': 'Test Video',
        'duration': 120,
        'thumbnail': 'http://thumb.com',
        'formats': [
            {'format_id': '22', 'ext': 'mp4', 'height': 720},
            {'format_id': '18', 'ext': 'mp4', 'height': 360}
        ]
    }

    # Mock the YoutubeDL class
    with patch('src.downloader.yt_dlp.YoutubeDL') as mock_ytdl_cls:
        # Mock the context manager behavior: with YoutubeDL() as ydl:
        mock_instance = mock_ytdl_cls.return_value
        mock_instance.__enter__.return_value = mock_instance
        
        # Mock extract_info method
        mock_instance.extract_info.return_value = mock_info
        
        url = "http://youtube.com/watch?v=video123"
        info = await extract_video_info(url)
        
        assert info['title'] == 'Test Video'
        assert info['duration'] == 120
        assert len(info['formats']) > 0
        # Since it runs in executor, we just check if it was called
        mock_instance.extract_info.assert_called_with(url, download=False)

@pytest.mark.asyncio
async def test_extract_video_info_failure():
    with patch('src.downloader.yt_dlp.YoutubeDL') as mock_ytdl_cls:
        mock_instance = mock_ytdl_cls.return_value
        mock_instance.__enter__.return_value = mock_instance
        
        # Simulate an exception during extraction
        mock_instance.extract_info.side_effect = Exception("Download Error")
        
        url = "http://invalid-url.com"
        with pytest.raises(Exception):
            await extract_video_info(url)
