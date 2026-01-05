"""
API authentication module for REST endpoints.
"""
import os
import logging
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from typing import Optional

logger = logging.getLogger(__name__)

# API Key header configuration
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


def get_api_key() -> Optional[str]:
    """Get the configured API key from environment."""
    return os.getenv("API_KEY")


async def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Verify the API key from request header.
    
    Args:
        api_key: API key from request header
        
    Returns:
        The verified API key
        
    Raises:
        HTTPException: If API key is invalid or missing
    """
    configured_key = get_api_key()
    
    # If no API key is configured, allow all requests
    if not configured_key:
        logger.warning("No API_KEY configured - API authentication is disabled!")
        return "no-auth"
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key"
        )
    
    if api_key != configured_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API key"
        )
    
    return api_key


def is_api_auth_enabled() -> bool:
    """Check if API authentication is enabled."""
    return bool(get_api_key())
