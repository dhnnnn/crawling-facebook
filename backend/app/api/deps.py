from fastapi import Security, HTTPException, status
from fastapi.security.api_key import APIKeyHeader
from ..config import Config

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    """
    Dependency to validate API Key from X-API-Key header.
    """
    if api_key_header == Config.API_KEY:
        return api_key_header
    
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Could not validate API Key",
    )
