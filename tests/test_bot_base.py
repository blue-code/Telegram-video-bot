import pytest
from unittest.mock import AsyncMock, MagicMock
from src.bot import start, help_command

@pytest.mark.asyncio
async def test_start_handler():
    # Mock Update and Context
    update = AsyncMock()
    update.effective_message.reply_text = AsyncMock()
    context = MagicMock()
    
    await start(update, context)
    
    # Check if reply_text was called with a welcome message (energetic persona)
    args, kwargs = update.effective_message.reply_text.call_args
    message = args[0]
    assert "반가워요" in message or "Welcome" in message or "🚀" in message
    assert update.effective_message.reply_text.called

@pytest.mark.asyncio
async def test_help_handler():
    # Mock Update and Context
    update = AsyncMock()
    update.effective_message.reply_text = AsyncMock()
    context = MagicMock()
    
    await help_command(update, context)
    
    # Check if reply_text was called with help instructions
    args, kwargs = update.effective_message.reply_text.call_args
    message = args[0]
    assert "도움말" in message or "Help" in message or "URL" in message
    assert update.effective_message.reply_text.called
