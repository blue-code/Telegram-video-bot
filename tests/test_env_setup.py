import os
import pytest
from dotenv import load_dotenv

def test_env_file_exists():
    assert os.path.exists(".env"), ".env file should exist"

def test_env_variables_loaded():
    load_dotenv()
    assert os.getenv("TELEGRAM_BOT_TOKEN") is not None, "TELEGRAM_BOT_TOKEN should be set"
    assert os.getenv("MONGO_URI") is not None, "MONGO_URI should be set"

def test_dependencies_installed():
    import telegram
    import motor
    import yt_dlp
    assert telegram
    assert motor
    assert yt_dlp
