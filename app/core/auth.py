import secrets
from typing import Optional
from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader
from app.config import settings

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def verify_audit_api_key(
    api_key: Optional[str] = Security(api_key_header)
) -> str:
    """
    Authenticate audit creation and management endpoints via the X-API-Key header.
    
    Uses constant-time comparison (secrets.compare_digest) to prevent timing attacks.
    Configured via AUDIT_API_KEY in app/config.py.
    """
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing required API key in 'X-API-Key' header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    expected_key = settings.AUDIT_API_KEY
    if not expected_key or not secrets.compare_digest(api_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key provided.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return api_key
