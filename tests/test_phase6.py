import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.bot import handle_callback
import os

@pytest.mark.asyncio
async def test_upload_to_bin_channel():
    # Setup
    update = MagicMock()
    context = MagicMock()
    query = MagicMock()
    update.callback_query = query
    query.data = "dl|video123|format123|720p"
    query.message.chat_id = 12345
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    
    # Mock user_data
    context.user_data = {
        "video123": {
            "url": "http://test.com/video",
            "title": "Test Video",
            "duration": 60,
            "thumbnail": "http://thumb.com"
        }
    }

    # Mock environment variables
    with patch.dict(os.environ, {"BIN_CHANNEL_ID": "-1001234567890", "TELEGRAM_BOT_TOKEN": "test_token"}):
        # Mock dependencies
        with patch('src.bot.download_video', new_callable=AsyncMock) as mock_download, \
             patch('src.bot.split_video', new_callable=AsyncMock) as mock_split, \
             patch('src.bot.save_video_metadata', new_callable=AsyncMock) as mock_save, \
             patch('builtins.open', new_callable=MagicMock):
            
            mock_download.return_value = "test_video.mp4"
            mock_split.return_value = ["test_video.mp4"]
            
            # Mock bot methods
            context.bot.send_video = AsyncMock()
            context.bot.send_audio = AsyncMock()
            
            # Mock return from Bin Channel upload
            mock_bin_msg = MagicMock()
            mock_bin_msg.video.file_id = "permanent_file_id_from_bin"
            
            # Mock return from User upload (we still want to verify it sends to user)
            mock_user_msg = MagicMock()
            
            # Configure side_effect for send_video to distinguish calls
            # First call (Bin Channel), Second call (User)
            context.bot.send_video.side_effect = [mock_bin_msg, mock_user_msg]

            # Execute
            await handle_callback(update, context)
            
            # Verify
            # 1. Check if uploaded to Bin Channel first
            assert context.bot.send_video.call_count >= 2
            
            # First call should be to Bin Channel
            args_bin, kwargs_bin = context.bot.send_video.call_args_list[0]
            assert kwargs_bin['chat_id'] == -1001234567890
            
            # Second call should be to User using the ID from Bin Channel
            args_user, kwargs_user = context.bot.send_video.call_args_list[1]
            assert kwargs_user['chat_id'] == 12345
            assert kwargs_user['video'] == "permanent_file_id_from_bin"
            
            # 2. Check if metadata saved uses the Bin Channel file ID
            mock_save.assert_called_once()
            saved_data = mock_save.call_args[0][0]
            assert saved_data['file_id'] == "permanent_file_id_from_bin"
