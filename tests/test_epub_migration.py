import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from src.epub_migration import migrate_epub_series

class TestEpubMigration(unittest.IsolatedAsyncioTestCase):
    @patch('src.db.get_files', new_callable=AsyncMock)
    @patch('src.db.get_database', new_callable=AsyncMock)
    async def test_migrate_epub_series(self, mock_get_db, mock_get_files):
        # Mock get_files response
        mock_get_files.side_effect = [
            [
                {'id': 1, 'user_id': 100, 'file_name': 'Title - 01.epub', 'metadata': {}},
                {'id': 2, 'user_id': 100, 'file_name': 'JustBook.epub', 'metadata': {}},
                {'id': 3, 'user_id': 100, 'file_name': 'Series 2.epub', 'metadata': {'series': 'OldSeries'}}
            ],
            [] # End of loop
        ]

        # Mock DB update
        mock_sb = MagicMock()
        mock_get_db.return_value = mock_sb
        
        # Mock chain: table().update().eq().execute()
        mock_execute = AsyncMock()
        mock_eq = MagicMock()
        mock_eq.execute = mock_execute
        mock_update = MagicMock()
        mock_update.eq.return_value = mock_eq
        mock_table = MagicMock()
        mock_table.update.return_value = mock_update
        mock_sb.table.return_value = mock_table

        # Run migration
        count = await migrate_epub_series()

        # Assertions
        # extract_series_info falls back to filename as series name if no pattern matches.
        # So "JustBook.epub" -> series="JustBook", volume=None.
        # All 3 files will be updated with series info.
        self.assertEqual(count, 3) 
        
        # Verify update calls
        self.assertEqual(mock_execute.call_count, 3)
