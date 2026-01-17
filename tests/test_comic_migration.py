import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from src.comic_migration import migrate_comic_series

class TestComicMigration(unittest.IsolatedAsyncioTestCase):
    @patch('src.db.get_files', new_callable=AsyncMock)
    @patch('src.db.get_comic_by_file_id', new_callable=AsyncMock)
    @patch('src.db.save_comic_metadata', new_callable=AsyncMock)
    async def test_migrate_comic_series(self, mock_save, mock_get_comic, mock_get_files):
        # Mock get_files response
        mock_get_files.side_effect = [
            [
                {'id': 1, 'user_id': 100, 'file_name': 'Title - 01화.zip'},
                {'id': 2, 'user_id': 100, 'file_name': 'JustFile.txt'}, # Should be ignored
                {'id': 3, 'user_id': 100, 'file_name': 'OnePiece 100권.cbz'}
            ],
            [] # End of loop
        ]

        # Mock get_comic_by_file_id
        mock_get_comic.return_value = None # No existing metadata

        # Run migration
        count = await migrate_comic_series()

        # Assertions
        self.assertEqual(count, 2)
        
        # Verify save calls
        self.assertEqual(mock_save.call_count, 2)
        
        # Check first call (Title - 01화)
        args1, _ = mock_save.call_args_list[0]
        data1 = args1[0]
        self.assertEqual(data1['title'], 'Title 1권') # '화' usually maps to volume in our logic? 
        # Wait, extract_series_info returns (series, volume). 
        # In comic_migration.py: if volume: title = f"{series} {volume}권"
        # "Title - 01화" -> Series="Title", Volume=1. Title="Title 1권".
        # This seems to be the current logic in comic_migration.py.
        # Ideally it might be "Title 1화" if we distinguish types, but currently schema uses 'volume' (int).
        self.assertEqual(data1['series'], 'Title')
        self.assertEqual(data1['volume'], 1)
        
        # Check second call (OnePiece 100권)
        args2, _ = mock_save.call_args_list[1]
        data2 = args2[0]
        self.assertEqual(data2['title'], 'OnePiece 100권')
        self.assertEqual(data2['series'], 'OnePiece')
        self.assertEqual(data2['volume'], 100)
