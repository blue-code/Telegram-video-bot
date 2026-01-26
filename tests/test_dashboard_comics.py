import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi import Request
from src.server import dashboard_page

class TestDashboardComics(unittest.IsolatedAsyncioTestCase):
    @patch('src.user_manager.get_user_stats', new_callable=AsyncMock)
    @patch('src.db.get_user_videos', new_callable=AsyncMock)
    @patch('src.db.get_recent_reading', new_callable=AsyncMock)
    @patch('src.db.get_recent_comic_reading', new_callable=AsyncMock)
    @patch('src.db.get_database', new_callable=AsyncMock)
    @patch('src.server.templates.TemplateResponse')
    async def test_dashboard_page_with_comics(self, mock_render, mock_db, mock_recent_comics, mock_recent_epub, mock_videos, mock_stats):
        # Mock statistics
        mock_stats.return_value = {'video_count': 10, 'user': {'total_downloads': 5, 'daily_quota': 10, 'downloads_today': 0}, 'total_storage': 1024*1024*100}
        mock_videos.return_value = []
        mock_recent_epub.return_value = None
        
        # Mock recent comics
        mock_recent_comics.return_value = [
            {
                'file_id': 123,
                'current_page': 5,
                'updated_at': '2026-01-17T10:00:00Z',
                'comics': {
                    'title': 'Test Comic',
                    'series': 'Test Series',
                    'page_count': 50,
                    'files': {'file_name': 'test.zip'}
                }
            }
        ]

        # Mock request
        request = MagicMock(spec=Request)
        
        # Call dashboard_page
        await dashboard_page(request, 12345)

        # Verify TemplateResponse was called with recent_comics
        self.assertTrue(mock_render.called)
        args, kwargs = mock_render.call_args
        context = args[1]
        
        self.assertIn('recent_comics', context)
        self.assertEqual(len(context['recent_comics']), 1)
        self.assertEqual(context['recent_comics'][0]['title'], 'Test Comic')
        self.assertEqual(context['recent_comics'][0]['current_page'], 5)
        self.assertEqual(context['recent_comics'][0]['total_pages'], 50)
