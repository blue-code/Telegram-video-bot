import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from src.db import get_book_series

@pytest.mark.asyncio
async def test_get_book_series_returns_first_book_id():
    """
    Verify that get_book_series returns 'first_book_id' for each series.
    """
    with patch("src.db.get_database", new_callable=AsyncMock) as mock_get_db:
        mock_client = MagicMock() 
        mock_get_db.return_value = mock_client
        
        # Mock the Supabase query chain
        mock_table = MagicMock()
        mock_client.table.return_value = mock_table
        
        mock_select = MagicMock()
        mock_table.select.return_value = mock_select
        
        # Chaining - CRITICAL: Must mock ALL intermediate methods called
        mock_select.eq.return_value = mock_select
        mock_select.order.return_value = mock_select
        mock_select.limit.return_value = mock_select
        
        # Mock execute to be an AsyncMock
        mock_execute = AsyncMock()
        mock_select.execute = mock_execute
        
        mock_result = MagicMock()
        mock_result.data = [
            {
                "id": 101,
                "file_name": "Book A.epub",
                "created_at": "2026-01-01T10:00:00",
                "metadata": {"series": "Series A", "volume": 1}
            },
            {
                "id": 201,
                "file_name": "Book B1.epub",
                "created_at": "2026-01-02T10:00:00",
                "metadata": {"series": "Series B", "volume": 1}
            },
            {
                "id": 202,
                "file_name": "Book B2.epub",
                "created_at": "2026-01-03T10:00:00",
                "metadata": {"series": "Series B", "volume": 2}
            }
        ]
        mock_execute.return_value = mock_result
        
        # Execute
        results = await get_book_series(user_id=123)
        
        # Assertions
        assert len(results) == 2
        
        # Find Series A
        series_a = next((s for s in results if s["series"] == "Series A"), None)
        assert series_a is not None
        assert series_a["count"] == 1
        # This is expected to FAIL until implementation is updated
        assert "first_book_id" in series_a, "first_book_id should be present in series data"
        assert series_a["first_book_id"] == 101
        
        # Find Series B
        series_b = next((s for s in results if s["series"] == "Series B"), None)
        assert series_b is not None
        assert "first_book_id" in series_b
        assert series_b["first_book_id"] == 201
