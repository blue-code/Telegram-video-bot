import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from telegram import Update, User, Chat, Message
from src.bot import handle_message

@pytest.mark.asyncio
async def test_resend_cached_video_single_part():
    # Setup
    update = MagicMock(spec=Update)
    context = MagicMock()
    
    # Mock message
    message = MagicMock(spec=Message)
    message.text = "https://youtube.com/watch?v=single"
    message.chat_id = 123
    update.effective_message = message
    
    # Mock reply_text and reply_video
    message.reply_text = AsyncMock()
    message.reply_video = AsyncMock()

    # Mock DB return
    mock_video_data = {
        "url": "https://youtube.com/watch?v=single",
        "file_id": "file_id_single",
        "title": "Single Part Video",
        "duration": 60,
        "metadata": {}
    }

    with patch('src.bot.get_video_by_url', new_callable=AsyncMock) as mock_get_db:
        mock_get_db.return_value = mock_video_data
        
        # Execute
        await handle_message(update, context)
        
        # Verify
        mock_get_db.assert_called_once_with("https://youtube.com/watch?v=single")
        message.reply_video.assert_called_once()
        args, kwargs = message.reply_video.call_args
        assert kwargs['video'] == "file_id_single"
        assert "다시 보기" in kwargs['caption']

@pytest.mark.asyncio
async def test_resend_cached_video_multi_part():
    # Setup
    update = MagicMock(spec=Update)
    context = MagicMock()
    
    # Mock message
    message = MagicMock(spec=Message)
    message.text = "https://youtube.com/watch?v=multi"
    message.chat_id = 123
    update.effective_message = message
    
    # Mock reply_text and reply_video
    message.reply_text = AsyncMock()
    message.reply_video = AsyncMock()
    message.reply_audio = AsyncMock()

    # Mock DB return with multiple parts in metadata
    mock_video_data = {
        "url": "https://youtube.com/watch?v=multi",
        "file_id": "file_id_part1", # Primary ID (for backward compatibility)
        "title": "Multi Part Video",
        "duration": 120,
        "metadata": {
            "parts": [
                {"file_id": "file_id_part1", "type": "video"},
                {"file_id": "file_id_part2", "type": "video"}
            ]
        }
    }

    with patch('src.bot.get_video_by_url', new_callable=AsyncMock) as mock_get_db:
        mock_get_db.return_value = mock_video_data
        
        # Execute
        await handle_message(update, context)
        
        # Verify
        mock_get_db.assert_called_once_with("https://youtube.com/watch?v=multi")
        
        # Should call reply_video twice
        assert message.reply_video.call_count == 2
        
        # Check call arguments
        calls = message.reply_video.call_args_list
        assert calls[0].kwargs['video'] == "file_id_part1"
        assert calls[1].kwargs['video'] == "file_id_part2"
