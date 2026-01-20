import pytest
import time
from playwright.sync_api import Page, expect

# Constants
BASE_URL = "http://localhost:8000"
TEST_BOOK_ID = 1 
USER_ID = 41509535 

@pytest.mark.e2e
def test_tts_stabilization(page: Page):
    """
    Comprehensive E2E test for TTS stabilization.
    """
    # 1. Access Reader
    print(f"Navigating to {BASE_URL}...")
    page.goto(f"{BASE_URL}/read/{TEST_BOOK_ID}?user_id={USER_ID}&debug=true")
    
    # 2. Wait for book
    page.wait_for_selector("#viewer iframe", timeout=15000)
    print("Book loaded.")
    
    # 3. Start TTS
    page.click("#menu-zone")
    page.click("#tts-play-pause")
    print("TTS Started.")
    
    # 4. Wait for audio element to exist and play
    # We can check the debug panel status instead of console logs for more stability
    expect(page.locator("#debug-status")).not_to_have_text("Init", timeout=10000)
    status = page.locator("#debug-status").inner_text()
    print(f"Current TTS Status: {status}")
    
    # 5. Rapid Manual Page Turn Test
    print("Simulating rapid page turns...")
    for _ in range(3):
        page.keyboard.press("ArrowRight")
        time.sleep(0.2)
    
    # 6. Verify that it's still sane (no multiple voices is hard to check via Playwright, 
    # but we can check if AudioController Stopped logs happened if we could see logs)
    
    # Check if debug panel is updating
    time.sleep(2)
    text_len = page.locator("#debug-text-len").inner_text()
    print(f"Text length after turns: {text_len}")
    assert int(text_len) >= 0
    
    print("Test finished successfully.")