import unittest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from src.server import app

class TestBookSeries(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    @patch('src.db.get_book_series', new_callable=AsyncMock)
    def test_book_series_list_route(self, mock_get_series):
        mock_get_series.return_value = []
        response = self.client.get("/books/12345")
        self.assertEqual(response.status_code, 200)
        self.assertIn("eBook 라이브러리", response.text)

    @patch('src.db.get_books_by_series', new_callable=AsyncMock)
    def test_book_series_detail_route(self, mock_get_books):
        mock_get_books.return_value = []
        response = self.client.get("/books/series/12345/TestSeries")
        self.assertEqual(response.status_code, 200)
        self.assertIn("TestSeries", response.text)

    @patch('src.db.get_files', new_callable=AsyncMock)
    @patch('src.db.count_files', new_callable=AsyncMock)
    def test_book_files_route(self, mock_count, mock_get_files):
        mock_get_files.return_value = []
        mock_count.return_value = 0
        response = self.client.get("/books/files/12345")
        self.assertEqual(response.status_code, 200)
        self.assertIn("eBooks File List", response.text)

    def test_default_redirect(self):
        response = self.client.get("/books", follow_redirects=False)
        self.assertEqual(response.status_code, 307)
