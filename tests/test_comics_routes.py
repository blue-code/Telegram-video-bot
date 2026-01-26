import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from src.server import app

class TestComicsRoutes(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch('src.db.get_comic_series', new_callable=AsyncMock)
    def test_comic_series_list_route(self, mock_get_series):
        mock_get_series.return_value = []
        response = self.client.get("/comics/12345")
        # Should return 200 and render series list template
        self.assertEqual(response.status_code, 200)
        self.assertIn("만화책 시리즈", response.text)

    @patch('src.db.get_comics', new_callable=AsyncMock)
    @patch('src.db.count_comics', new_callable=AsyncMock)
    def test_comic_files_route(self, mock_count, mock_get_comics):
        mock_get_comics.return_value = []
        mock_count.return_value = 0
        response = self.client.get("/comics/files/12345")
        # Should return 200 and render flat file list template
        self.assertEqual(response.status_code, 200)
        self.assertIn("만화책 파일 목록", response.text)

    def test_default_redirect(self):
        response = self.client.get("/comics", follow_redirects=False)
        self.assertEqual(response.status_code, 307)
        self.assertTrue(response.headers['location'].startswith("/comics/"))
