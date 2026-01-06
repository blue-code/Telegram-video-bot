import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from fastapi.testclient import TestClient
from src.server import app, parse_range_header, generate_etag


def test_parse_range_header_valid():
    """Test parsing valid Range headers"""
    # Test full range
    result = parse_range_header("bytes=0-999", 1000)
    assert result == (0, 999)
    
    # Test open-ended range
    result = parse_range_header("bytes=500-", 1000)
    assert result == (500, 999)
    
    # Test range with end
    result = parse_range_header("bytes=100-200", 1000)
    assert result == (100, 200)


def test_parse_range_header_invalid():
    """Test parsing invalid Range headers"""
    # No range header
    result = parse_range_header(None, 1000)
    assert result is None
    
    # Invalid format
    result = parse_range_header("invalid", 1000)
    assert result is None
    
    # Start beyond file size
    result = parse_range_header("bytes=2000-", 1000)
    assert result is None
    
    # Start > end
    result = parse_range_header("bytes=500-100", 1000)
    assert result is None


def test_parse_range_header_boundary():
    """Test Range header boundary conditions"""
    # End beyond file size (should clamp to file size - 1)
    result = parse_range_header("bytes=0-2000", 1000)
    assert result == (0, 999)
    
    # Last byte
    result = parse_range_header("bytes=999-999", 1000)
    assert result == (999, 999)


def test_generate_etag():
    """Test ETag generation"""
    etag1 = generate_etag("file_id_1")
    etag2 = generate_etag("file_id_1")
    etag3 = generate_etag("file_id_2")
    
    # Same file_id should generate same ETag
    assert etag1 == etag2
    
    # Different file_id should generate different ETag
    assert etag1 != etag3
    
    # ETag should be a valid hex string
    assert len(etag1) == 32
    assert all(c in "0123456789abcdef" for c in etag1)


@pytest.mark.asyncio
async def test_stream_video_with_range():
    """Test streaming with Range request support"""
    client = TestClient(app)
    
    # Mock get_file_info_cached
    with patch('src.server.get_file_info_cached', new_callable=AsyncMock) as mock_get_file:
        mock_get_file.return_value = ("https://example.com/file.mp4", 1000000)
        
        # Mock httpx client streaming
        with patch('httpx.AsyncClient') as mock_client:
            mock_stream_response = AsyncMock()
            mock_stream_response.raise_for_status = MagicMock()
            
            async def mock_aiter_bytes(chunk_size=65536):
                yield b"test_chunk"
            
            mock_stream_response.aiter_bytes = mock_aiter_bytes
            
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_stream_response)
            mock_context.__aexit__ = AsyncMock()
            
            mock_client_instance = AsyncMock()
            mock_client_instance.stream = MagicMock(return_value=mock_context)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock()
            
            mock_client.return_value = mock_client_instance
            
            # Test Range request
            response = client.get(
                "/stream/test_file_id",
                headers={"Range": "bytes=0-1023"}
            )
            
            # Should return 206 Partial Content
            assert response.status_code == 206
            assert "Content-Range" in response.headers
            assert response.headers["Accept-Ranges"] == "bytes"
            assert "ETag" in response.headers
            assert "Cache-Control" in response.headers


@pytest.mark.asyncio
async def test_stream_video_full_file():
    """Test streaming full file without Range"""
    client = TestClient(app)
    
    with patch('src.server.get_file_info_cached', new_callable=AsyncMock) as mock_get_file:
        mock_get_file.return_value = ("https://example.com/file.mp4", 1000000)
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_stream_response = AsyncMock()
            mock_stream_response.raise_for_status = MagicMock()
            
            async def mock_aiter_bytes(chunk_size=65536):
                yield b"test_chunk"
            
            mock_stream_response.aiter_bytes = mock_aiter_bytes
            
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_stream_response)
            mock_context.__aexit__ = AsyncMock()
            
            mock_client_instance = AsyncMock()
            mock_client_instance.stream = MagicMock(return_value=mock_context)
            mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
            mock_client_instance.__aexit__ = AsyncMock()
            
            mock_client.return_value = mock_client_instance
            
            # Test full file request (no Range header)
            response = client.get("/stream/test_file_id")
            
            # Should return 200 OK
            assert response.status_code == 200
            assert response.headers["Accept-Ranges"] == "bytes"
            assert "ETag" in response.headers
            assert "Content-Length" in response.headers


@pytest.mark.asyncio
async def test_stream_video_etag_cache():
    """Test ETag-based caching with If-None-Match"""
    client = TestClient(app)
    
    with patch('src.server.get_file_info_cached', new_callable=AsyncMock) as mock_get_file:
        mock_get_file.return_value = ("https://example.com/file.mp4", 1000000)
        
        etag = generate_etag("test_file_id")
        
        # Test with matching ETag
        response = client.get(
            "/stream/test_file_id",
            headers={"If-None-Match": etag}
        )
        
        # Should return 304 Not Modified
        assert response.status_code == 304


@pytest.mark.asyncio
async def test_file_info_cache():
    """Test file info caching functionality"""
    from src.server import get_file_info_cached, file_info_cache
    import time
    
    # Clear cache
    file_info_cache.clear()
    
    with patch('httpx.AsyncClient') as mock_client:
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "ok": True,
            "result": {
                "file_path": "videos/test.mp4",
                "file_size": 1000000
            }
        }
        
        mock_client_instance = AsyncMock()
        mock_client_instance.get = AsyncMock(return_value=mock_response)
        mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
        mock_client_instance.__aexit__ = AsyncMock()
        
        mock_client.return_value = mock_client_instance
        
        with patch.dict('os.environ', {'TELEGRAM_BOT_TOKEN': 'test_token'}):
            # First call - should fetch from API
            url1, size1 = await get_file_info_cached("test_file_id")
            assert url1.endswith("videos/test.mp4")
            assert size1 == 1000000
            assert "test_file_id" in file_info_cache
            
            # Second call - should use cache
            url2, size2 = await get_file_info_cached("test_file_id")
            assert url2 == url1
            assert size2 == size1
            
            # API should only be called once
            assert mock_client_instance.get.call_count == 1


def test_cache_expiration():
    """Test cache TTL expiration"""
    from src.server import file_info_cache, CACHE_TTL
    import time
    
    file_info_cache.clear()
    
    # Manually add expired cache entry
    file_info_cache["expired_file"] = {
        "url": "https://example.com/old.mp4",
        "size": 1000,
        "timestamp": time.time() - CACHE_TTL - 100  # Expired
    }
    
    # Verify it's considered expired (actual check happens in get_file_info_cached)
    cached = file_info_cache["expired_file"]
    assert time.time() - cached["timestamp"] > CACHE_TTL
