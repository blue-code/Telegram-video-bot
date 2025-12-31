import pytest
import os
from unittest.mock import patch, MagicMock, AsyncMock
from src.splitter import split_video

@pytest.mark.asyncio
async def test_split_video_no_split_needed():
    # Test case where video is small enough
    file_path = "small_video.mp4"
    max_size = 1024 * 1024 * 10 # 10MB
    
    with patch('os.path.getsize') as mock_getsize, \
         patch('os.path.exists') as mock_exists:
        
        mock_getsize.return_value = 1024 * 1024 * 5 # 5MB
        mock_exists.return_value = True
        
        result = await split_video(file_path, max_size_bytes=max_size)
        assert result == [file_path]

@pytest.mark.asyncio
async def test_split_video_needs_split():
    # Test case where video needs splitting
    file_path = "large_video.mp4"
    max_size = 1024 * 1024 * 10 # 10MB
    
    with patch('os.path.getsize') as mock_getsize, \
         patch('os.path.exists') as mock_exists, \
         patch('src.splitter.get_video_duration') as mock_duration, \
         patch('asyncio.create_subprocess_exec') as mock_subprocess:
        
        mock_getsize.return_value = 1024 * 1024 * 25 # 25MB (Should result in 3 parts)
        mock_exists.return_value = True
        mock_duration.return_value = 300 # 300 seconds
        
        # Mock subprocess to simulate success
        mock_process = MagicMock()
        mock_process.returncode = 0
        # communicate must be an async method returning a tuple
        mock_process.communicate = AsyncMock(return_value=(b'', b''))
        mock_subprocess.return_value = mock_process
        
        result = await split_video(file_path, max_size_bytes=max_size)
        
        assert len(result) == 3
        # Check if ffmpeg was called
        assert mock_subprocess.called
