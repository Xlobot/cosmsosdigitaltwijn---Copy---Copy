"""
COSMOS Shared JWT Token Engine
==============================
Generates and validates JSON Web Tokens using PyJWT with HS256.
Enforces a 15-minute access token lifespan per specification.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional
import jwt
from fastapi import HTTPException, status

from .config import JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRATION_MINUTES


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Generate a signed JWT token with standard payload claims and a 15-minute expiry.
    """
    to_encode = data.copy()
    now_utc = datetime.now(timezone.utc)
    
    if expires_delta is not None:
        expire_utc = now_utc + expires_delta
    else:
        expire_utc = now_utc + timedelta(minutes=JWT_EXPIRATION_MINUTES)
    
    to_encode.update({
        "exp": expire_utc,
        "iat": now_utc,
        "nbf": now_utc,
        "jti": str(uuid.uuid4()),
    })
    
    encoded_jwt = jwt.encode(to_encode, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return encoded_jwt


def verify_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate a JWT access token.
    Raises HTTPException (401) on expiration or signature errors.
    """
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        username: Optional[str] = payload.get("sub")
        if not username:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token payload is missing subject claim ('sub').",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session has expired. Please log in again (token exceeded 15 minute lifetime).",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as err:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(err)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
