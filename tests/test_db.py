import pytest
from unittest.mock import patch, MagicMock, AsyncMock

@pytest.mark.asyncio
async def test_get_database_structure():
    from src.db import get_database, close_database
    
    with patch("src.db.create_async_client") as mock_create:
        mock_client = AsyncMock()
        mock_create.return_value = mock_client
        
        db = await get_database()
        assert db is not None
        assert db == mock_client
        
        await close_database()

@pytest.mark.asyncio
async def test_crud_operations():
    from src.db import save_video_metadata, get_video_by_url, get_video_by_file_id
    
    with patch("src.db.create_async_client") as mock_create:
        mock_client = AsyncMock()
        mock_create.return_value = mock_client
        
        # Mock table builder pattern for upsert
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        
        mock_upsert = MagicMock()
        mock_table.upsert.return_value = mock_upsert
        
        mock_execute = AsyncMock()
        mock_upsert.execute.return_value = mock_execute
        mock_execute.data = [{"id": 1}]

        # Test Save (Upsert)
        video_data = {"url": "http://test.com", "title": "Test Video"}
        await save_video_metadata(video_data)
        mock_table.upsert.assert_called_with(video_data, on_conflict="url")

        # Mock select builder pattern
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        
        mock_eq = MagicMock()
        mock_select.eq.return_value = mock_eq
        
        mock_eq.execute = AsyncMock()
        mock_eq.execute.return_value = mock_execute
        mock_execute.data = [{"url": "http://test.com", "title": "Test Video"}]

        # Test Get by URL
        result = await get_video_by_url("http://test.com")
        mock_table.select.assert_called_with("*")
        mock_select.eq.assert_called_with("url", "http://test.com")
        assert result["url"] == "http://test.com"

        # Test Get by File ID
        mock_execute.data = [{"file_id": "file_123"}]
        result = await get_video_by_file_id("file_123")
        mock_select.eq.assert_called_with("file_id", "file_123")
        assert result["file_id"] == "file_123"