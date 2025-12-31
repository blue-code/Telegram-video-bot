import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.bot import handle_message, handle_callback

@pytest.mark.asyncio
async def test_handle_message_with_url():
    # Mock Update and Context
    update = AsyncMock()
    update.effective_message.text = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    
    # status_message mock
    status_message = AsyncMock()
    update.effective_message.reply_text = AsyncMock(return_value=status_message)
    context = MagicMock()
    
    mock_info = {
        'id': 'dQw4w9WgXcQ',
        'title': 'Rick Astley - Never Gonna Give You Up',
        'duration': 212,
        'thumbnail': 'http://thumb.com',
        'formats': [
            {'format_id': '22', 'ext': 'mp4', 'height': 720},
            {'format_id': '18', 'ext': 'mp4', 'height': 360}
        ]
    }
    
    with patch('src.bot.extract_video_info', new_callable=AsyncMock) as mock_extract, \
         patch('src.bot.get_video_by_url', new_callable=AsyncMock) as mock_get_db:
        
        mock_extract.return_value = mock_info
        mock_get_db.return_value = None # Not in DB yet
        
        await handle_message(update, context)
        
        assert mock_extract.called
        # Check if status message was edited with buttons
        args, kwargs = status_message.edit_text.call_args
        assert "Rick Astley" in args[0]
        assert "reply_markup" in kwargs
        assert len(kwargs['reply_markup'].inline_keyboard) > 0

@pytest.mark.asyncio
async def test_handle_message_no_url():
    update = AsyncMock()
    update.effective_message.text = "Hello there"
    update.effective_message.reply_text = AsyncMock()
    context = MagicMock()
    
    await handle_message(update, context)
    
    args, kwargs = update.effective_message.reply_text.call_args
    assert "링크가 보이지 않아요" in args[0]

@pytest.mark.asyncio
async def test_handle_callback():
    update = AsyncMock()
    update.callback_query.data = "dl|video123|22|720"
    update.callback_query.answer = AsyncMock()
    update.callback_query.edit_message_text = AsyncMock()
    context = MagicMock()
    
    await handle_callback(update, context)
    
    assert update.callback_query.answer.called
    args, kwargs = update.callback_query.edit_message_text.call_args
    assert "720 화질" in args[0]
    assert "🚀" in args[0]