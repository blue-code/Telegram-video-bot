import unittest
from unittest.mock import MagicMock
from fastapi.templating import Jinja2Templates
from fastapi import Request

class TestTemplatesRender(unittest.TestCase):
    def setUp(self):
        self.templates = Jinja2Templates(directory="templates")
        self.request = MagicMock(spec=Request)

    def test_comic_reader_render(self):
        context = {
            "request": self.request,
            "file_id": 1,
            "user_id": 1,
            "title": "Test Comic",
            "series": "Test Series",
            "page_count": 10,
            "current_page": 0,
            "settings": "{}"
        }
        response = self.templates.TemplateResponse("comic_reader.html", context)
        self.assertIn(b"Test Comic", response.body)
        self.assertIn(b"webtoon-mode", response.body) # Check for css class logic

    def test_reader_render(self):
        context = {
            "request": self.request,
            "file_id": 1,
            "user_id": 1,
            "title": "Test Book",
            "book_url": "/api/test",
            "initial_cfi": "None"
        }
        response = self.templates.TemplateResponse("reader.html", context)
        self.assertIn(b"Test Book", response.body)
        self.assertIn(b"timer-modal", response.body) # Check for new timer modal

    def test_books_series_render_direct_link(self):
        """
        Test that single-book series render a direct link to the reader,
        while multi-book series render a link to the series detail page.
        """
        context = {
            "request": self.request,
            "user_id": 123,
            "series_list": [
                {
                    "series": "SingleBook",
                    "count": 1,
                    "first_book_id": 101,
                    "cover_url": None
                },
                {
                    "series": "MultiBook",
                    "count": 5,
                    "first_book_id": 201,
                    "cover_url": None
                }
            ]
        }
        response = self.templates.TemplateResponse("books_series.html", context)
        body = response.body.decode()
        
        # Check SingleBook link - Should be direct to reader
        # Note: The template likely uses Jinja2 logic to verify this.
        self.assertIn("window.location.href='/books/read/101'", body)
        
        # Check MultiBook link - Should remain as series view
        self.assertIn("window.location.href='/books/series/123/MultiBook'", body)
