

import os
import logging
from typing import Optional

from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader

log = logging.getLogger("polymath.api.auth")

# Define the expected header name
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key_header: Optional[str] = Security(API_KEY_HEADER)) -> None:
    """
    FastAPI dependency to validate the incoming X-API-Key header.
    
    If POLYMATH_API_KEY is not set in the environment, auth is disabled.
    If it is set, the incoming header must match exactly.
    """
    expected_key = os.getenv("POLYMATH_API_KEY")
    
    if not expected_key:
        # Auth disabled
        return
        
    if not api_key_header:
        log.warning("Auth failure: Missing X-API-Key header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header",
        )
        
    if api_key_header != expected_key:
        log.warning("Auth failure: Invalid API Key provided")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid API Key",
        )
