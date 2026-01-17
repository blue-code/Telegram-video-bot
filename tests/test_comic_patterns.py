import unittest
from src.comic_parser import extract_series_info

class TestComicPatterns(unittest.TestCase):
    def test_existing_patterns(self):
        # "원피스 1권.zip" -> "원피스", 1
        series, vol = extract_series_info("원피스 1권.zip")
        self.assertEqual(series, "원피스")
        self.assertEqual(vol, 1)

        # "OnePiece vol.1.zip" -> "OnePiece", 1
        series, vol = extract_series_info("OnePiece vol.1.zip")
        self.assertEqual(series, "OnePiece")
        self.assertEqual(vol, 1)

    def test_new_pattern_n_hwa(self):
        # "그거 그렇게 하는거 아닌데 9화.zip" -> "그거 그렇게 하는거 아닌데", 9
        series, vol = extract_series_info("그거 그렇게 하는거 아닌데 9화.zip")
        self.assertEqual(series, "그거 그렇게 하는거 아닌데")
        self.assertEqual(vol, 9)

        # "그거 그렇게 하는거 아닌데 10화.zip" -> "그거 그렇게 하는거 아닌데", 10
        series, vol = extract_series_info("그거 그렇게 하는거 아닌데 10화.zip")
        self.assertEqual(series, "그거 그렇게 하는거 아닌데")
        self.assertEqual(vol, 10)

    def test_new_pattern_hyphen_hwa(self):
        # "제목 - 01화.zip" -> "제목", 1
        series, vol = extract_series_info("제목 - 01화.zip")
        self.assertEqual(series, "제목")
        self.assertEqual(vol, 1)

    def test_new_pattern_bracket(self):
        # "[작가명] 제목 01.zip" -> "제목", 1
        series, vol = extract_series_info("[작가명] 제목 01.zip")
        self.assertEqual(series, "제목")
        self.assertEqual(vol, 1)

    def test_new_pattern_parenthesis(self):
        # "제목 (01).zip" -> "제목", 1
        series, vol = extract_series_info("제목 (01).zip")
        self.assertEqual(series, "제목")
        self.assertEqual(vol, 1)