import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
from src.server import app

client = TestClient(app)

@pytest.mark.asyncio
async def test_tts_synthesize_success():
    """Test successful TTS synthesis"""
    mock_communicate = MagicMock()
    
    # Mock stream to return an async generator
    async def mock_stream():
        yield {"type": "audio", "data": b"audio_chunk_1"}
        yield {"type": "audio", "data": b"audio_chunk_2"}
        yield {"type": "WordBoundary", "offset": 0, "duration": 100, "text": "hello"}
        
    mock_communicate.stream.return_value = mock_stream()
    
    with patch("edge_tts.Communicate", return_value=mock_communicate):
        response = client.post("/api/tts/synthesize", json={
            "text": "Hello world",
            "voice": "ko-KR-SunHiNeural"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "audio" in data
        assert "subtitle" in data
        assert len(data["subtitle"]) == 1
        assert data["subtitle"][0]["text"] == "hello"

@pytest.mark.asyncio
async def test_tts_synthesize_empty_text():
    """Test TTS with empty text"""
    response = client.post("/api/tts/synthesize", json={
        "text": "",
        "voice": "ko-KR-SunHiNeural"
    })
    assert response.status_code == 400
    assert "Text cannot be empty" in response.json()["detail"]

@pytest.mark.asyncio
async def test_tts_synthesize_long_text():
    """Test TTS with text exceeding limit"""
    long_text = "a" * 1001
    response = client.post("/api/tts/synthesize", json={
        "text": long_text,
        "voice": "ko-KR-SunHiNeural"
    })
    assert response.status_code == 400
    assert "Text too long" in response.json()["detail"]

@pytest.mark.asyncio
async def test_tts_synthesize_stream_error():
    """Test TTS error handling during stream"""
    mock_communicate = MagicMock()
    
    async def mock_stream_error():
        yield {"type": "audio", "data": b"chunk1"}
        raise Exception("Stream failed")
        
    mock_communicate.stream.return_value = mock_stream_error()
    
    with patch("edge_tts.Communicate", return_value=mock_communicate):
        response = client.post("/api/tts/synthesize", json={
            "text": "Error case",
            "voice": "ko-KR-SunHiNeural"
        })
        
        assert response.status_code == 500
        assert "TTS synthesis failed" in response.json()["detail"]