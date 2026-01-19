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
