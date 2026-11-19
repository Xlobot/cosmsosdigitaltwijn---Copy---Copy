"""
COSMOS Shared FastAPI Security Dependencies
===========================================
Provides dependency injection functions for route protection:
1. require_user_token: Verifies operator JWT bearer tokens (15-min expiry).
2. require_service_key: Enforces inter-service X-Service-Key header authentication.
3. require_user_or_service_key: Allows either a valid User JWT or X-Service-Key.
4. require_admin_role: Enforces that the caller is an authenticated Administrator.
5. require_permission: Enforces granular role-based permissions (or admin wildcard).
"""

import hmac
from typing import Optional, Dict, Any, List
from fastapi import Header, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .config import COSMOS_SERVICE_KEY, SERVICE_KEY_HEADER
from .tokens import verify_access_token
from .db import get_user_by_username

_bearer_scheme = HTTPBearer(auto_error=False)


def get_service_headers() -> Dict[str, str]:
    """Helper for building outgoing inter-service requests with the X-Service-Key header."""
    return {SERVICE_KEY_HEADER: COSMOS_SERVICE_KEY}


async def require_service_key(
    x_service_key: Optional[str] = Header(None, alias=SERVICE_KEY_HEADER)
) -> str:
    """
    Enforces inter-service authentication via the X-Service-Key header.
    Rejects unauthorized callers with HTTP 403 Forbidden.
    """
    if not x_service_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing required inter-service authentication header '{SERVICE_KEY_HEADER}'."
        )
    
    # Constant-time comparison to prevent timing attacks
    if not hmac.compare_digest(x_service_key.strip(), COSMOS_SERVICE_KEY.strip()):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Invalid '{SERVICE_KEY_HEADER}' presented."
        )
    
    return x_service_key


async def require_user_token(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme)
) -> Dict[str, Any]:
    """
    Extracts and validates the JWT Bearer token from the HTTP Authorization header.
    Rejects missing or expired tokens with HTTP 401 Unauthorized.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please provide a Bearer access token in the Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    payload = verify_access_token(token)
    username = payload.get("sub")
    
    user = get_user_by_username(username)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account no longer exists in system registry.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    perms = user.get("permissions")
    if not perms:
        perms = ["*"] if user.get("role") == "admin" else ["telemetry:read"]

    # Return user record stripped of sensitive password hash
    safe_user = {
        "id": user["id"],
        "username": user["username"],
        "role": user.get("role", "operator"),
        "permissions": perms,
        "created_at": user.get("created_at"),
        "token_claims": payload
    }
    return safe_user


async def require_user_or_service_key(
    x_service_key: Optional[str] = Header(None, alias=SERVICE_KEY_HEADER),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme)
) -> Dict[str, Any]:
    """
    Dual-mode authenticator: accepts either an inter-service X-Service-Key OR an operator JWT token.
    Used for endpoints that serve both UI dashboards and background microservice coordination.
    """
    # 1. Check Service Key first if provided
    if x_service_key:
        if hmac.compare_digest(x_service_key.strip(), COSMOS_SERVICE_KEY.strip()):
            return {
                "auth_type": "service",
                "identity": "cosmos_internal_service",
                "role": "admin",
                "permissions": ["*"]
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Invalid '{SERVICE_KEY_HEADER}' provided for service-level access."
            )

    # 2. Check User Bearer Token
    if credentials and credentials.credentials:
        payload = verify_access_token(credentials.credentials)
        username = payload.get("sub")
        user = get_user_by_username(username)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User account no longer exists in system registry.",
                headers={"WWW-Authenticate": "Bearer"},
            )
        perms = user.get("permissions")
        if not perms:
            perms = ["*"] if user.get("role") == "admin" else ["telemetry:read"]

        return {
            "auth_type": "user",
            "identity": user["username"],
            "role": user.get("role", "operator"),
            "permissions": perms,
            "user": {
                "id": user["id"],
                "username": user["username"],
                "role": user.get("role", "operator"),
                "permissions": perms
            }
        }

    # 3. Neither provided
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=f"Authentication required: Provide a valid JWT Bearer token or an inter-service '{SERVICE_KEY_HEADER}' header.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def require_admin_role(
    auth: Dict[str, Any] = Depends(require_user_or_service_key)
) -> Dict[str, Any]:
    """
    Enforces that only administrators (or internal system services) can access the endpoint.
    Non-admin users will receive HTTP 403 Forbidden.
    """
    role = auth.get("role")
    if role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required. Only administrators can perform this operation."
        )
    return auth


def require_permission(perm: str):
    """
    Dependency factory to check if caller has the required granular permission.
    - Admin users have full access to everything (role == 'admin' or '*' in permissions).
    - Internal services with X-Service-Key have full access.
    - Other users must have the specific permission listed in their permissions array.
    """
    async def _perm_checker(auth: Dict[str, Any] = Depends(require_user_or_service_key)) -> Dict[str, Any]:
        if auth.get("auth_type") == "service":
            return auth
        
        role = auth.get("role", "")
        perms = auth.get("permissions", [])
        
        if role == "admin" or "*" in perms or perm in perms:
            return auth
        
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: User '{auth.get('identity')}' lacks required permission '{perm}'."
        )
    return _perm_checker
