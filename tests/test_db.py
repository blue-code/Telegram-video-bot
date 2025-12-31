import pytest
import os
from unittest.mock import patch, MagicMock
# We will mock the actual DB connection for unit tests to avoid needing a real Mongo instance
# unless we use testcontainers or have a local instance.
# For this step, we just want to verify the module structure and connection logic exists.

# We need to set python path or install the package in editable mode.
# For now, let's assume we run pytest from root and src is discoverable if we add __init__.py
# or configure pytest pythonpath.

@pytest.mark.asyncio
async def test_get_database_structure():
    # This import will fail first
    from src.db import get_database, close_database
    
    # Mocking motor client
    with patch("src.db.AsyncIOMotorClient") as mock_client:
        mock_db = MagicMock()
        mock_client.return_value.get_database.return_value = mock_db
        
        db = await get_database()
        assert db is not None
        
        await close_database()
        mock_client.return_value.close.assert_called_once()

@pytest.mark.asyncio
async def test_crud_operations():
    from src.db import save_video_metadata, get_video_by_url, get_database
    from unittest.mock import AsyncMock
    
    with patch("src.db.AsyncIOMotorClient") as mock_client:
        mock_db = MagicMock()
        mock_collection = MagicMock()
        
        # Mocking the chain: client[DB_NAME][COLLECTION_NAME]
        mock_client.return_value.__getitem__.return_value = mock_db
        mock_db.__getitem__.return_value = mock_collection
        
        # Configure async methods
        mock_collection.insert_one = AsyncMock()
        mock_collection.find_one = AsyncMock()

        # Test Save
        video_data = {"url": "http://test.com", "title": "Test Video"}
        await save_video_metadata(video_data)
        mock_collection.insert_one.assert_called_with(video_data)
        
        # Test Get
        await get_video_by_url("http://test.com")
        mock_collection.find_one.assert_called_with({"url": "http://test.com"})

        # Test Get by File ID
        from src.db import get_video_by_file_id
        await get_video_by_file_id("file_123")
        mock_collection.find_one.assert_called_with({"file_id": "file_123"})
