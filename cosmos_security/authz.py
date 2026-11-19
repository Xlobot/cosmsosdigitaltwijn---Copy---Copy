"""
COSMOS Centralized Authorization (RBAC) Module
==============================================
Defines the single source of truth for Role-Based Access Control across all COSMOS services:
- Digital Twin Engine (:8000)
- Mission Intelligence Server (:8001)
- Telemetry Generator (:8080)

Role Hierarchy:
    viewer < analyst < operator < admin

Rules:
1. Deny by default: Every route declares its required role or service-key.
2. 401 for missing/invalid/expired/tampered tokens. 403 for insufficient or missing/unknown roles.
3. Service keys are never roles and cannot act as users. User tokens cannot access service-key routes.
4. All denials and admin actions are audit-logged (tokens and secrets are never logged).
"""

import hmac
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from fastapi import Header, Depends, HTTPException, status, Request, WebSocket
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from .config import COSMOS_SERVICE_KEY, SERVICE_KEY_HEADER
from .tokens import verify_access_token
from .dependencies import require_user_token, _bearer_scheme
from .db import get_user_by_username

# ---------------------------------------------------------------------------
# 1. ROLES & HIERARCHY
# ---------------------------------------------------------------------------
ROLE_VIEWER = "viewer"
ROLE_ANALYST = "analyst"
ROLE_OPERATOR = "operator"
ROLE_ADMIN = "admin"

ALL_ROLES: List[str] = [ROLE_VIEWER, ROLE_ANALYST, ROLE_OPERATOR, ROLE_ADMIN]

ROLE_HIERARCHY: Dict[str, int] = {
    ROLE_VIEWER: 1,
    ROLE_ANALYST: 2,
    ROLE_OPERATOR: 3,
    ROLE_ADMIN: 4,
}

# ---------------------------------------------------------------------------
# 2. CENTRAL PERMISSION TABLE (Single Source of Truth)
# ---------------------------------------------------------------------------
# Format: (Method, Path)
PERMISSION_TABLE: Dict[str, Any] = {
    "roles": {
        ROLE_VIEWER: [
            # Digital Twin (:8000)
            ("GET", "/api/status"),
            ("GET", "/api/generator/status"),
            ("GET", "/api/state"),
            ("GET", "/api/timeline"),
            ("GET", "/api/anomalies"),
            ("GET", "/api/dataset/all"),
            ("GET", "/api/models/info"),
            ("GET", "/api/mi/history"),
            ("GET", "/api/mi/health"),
            # Mission Intelligence (:8001)
            ("GET", "/"),
            ("GET", "/api/history"),
            ("GET", "/api/health"),
            # Telemetry Generator (:8080)
            ("GET", "/latest"),
            ("GET", "/rows"),
            ("GET", "/keys"),
            ("GET", "/schema"),
            ("GET", "/ws"),
            ("GET", "/stream"),
        ],
        ROLE_ANALYST: [
            # Digital Twin (:8000)
            ("POST", "/api/predict"),
            ("POST", "/api/fork"),
            ("POST", "/api/mi/assess"),
            ("POST", "/api/mi/trigger-assessment"),
            # Mission Intelligence (:8001)
            ("POST", "/api/assess"),
        ],
        ROLE_OPERATOR: [
            # Digital Twin (:8000)
            ("POST", "/api/mi/decision"),
            # Mission Intelligence (:8001)
            ("POST", "/api/decision"),
        ],
        ROLE_ADMIN: [
            # Digital Twin (:8000)
            ("POST", "/api/generator/inject-anomaly"),
            ("GET", "/api/auth/users"),
            ("POST", "/api/auth/users"),
            ("PUT", "/api/auth/users/{username}/permissions"),
            ("DELETE", "/api/auth/users/{username}"),
            # Telemetry Generator (:8080)
            ("POST", "/control/rate"),
            ("POST", "/control/pause"),
            ("POST", "/control/resume"),
            ("POST", "/control/reset"),
            ("POST", "/inject/anomaly"),
        ],
    },
    "service_key_or_admin": [
        # Digital Twin (:8000)
        ("POST", "/api/mi/push-state"),
        ("POST", "/api/mi/push-prediction"),
        ("POST", "/api/mi/push-recommendation"),
        # Mission Intelligence (:8001)
        ("POST", "/webhook/trigger-assessment"),
        ("POST", "/webhook/digital-twin/state"),
        ("POST", "/webhook/digital-twin/prediction"),
        ("POST", "/webhook/digital-twin/recommendation"),
    ],
    "public": [
        ("GET", "/healthz"),
        ("POST", "/api/auth/login"),
    ]
}

# ---------------------------------------------------------------------------
# 3. AUDIT LOGGING (Never logs tokens or secret keys)
# ---------------------------------------------------------------------------
audit_logger = logging.getLogger("cosmos.audit")
if not audit_logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("[%(levelname)s] %(name)s: %(message)s"))
    audit_logger.addHandler(_handler)
audit_logger.setLevel(logging.INFO)


def log_access_denied(user: str, role: str, route: str, reason: str = ""):
    """Audit log for access denials (user, role, route, time)."""
    now_iso = datetime.now(timezone.utc).isoformat()
    audit_logger.warning(
        f"[AUDIT DENIED] timestamp={now_iso} user='{user}' role='{role}' route='{route}' reason='{reason}'"
    )


def log_admin_action(user: str, route: str, action: str):
    """Audit log for sensitive administrator actions."""
    now_iso = datetime.now(timezone.utc).isoformat()
    audit_logger.info(
        f"[AUDIT ADMIN] timestamp={now_iso} user='{user}' route='{route}' action='{action}'"
    )


# Granular permission requirements for sensitive operations
ROUTE_PERMISSION_MAP: Dict[str, str] = {
    "/api/predict": "predict:run",
    "/api/fork": "scenarios:fork",
    "/api/generator/inject-anomaly": "anomalies:inject",
    "/api/mi/assess": "mission_intel:assess",
    "/api/mi/trigger-assessment": "mission_intel:assess",
    "/api/assess": "mission_intel:assess",
    "/api/mi/decision": "mission_intel:decide",
    "/api/decision": "mission_intel:decide",
}


# ---------------------------------------------------------------------------
# 4. DEPENDENCY: require_role(min_role)
# ---------------------------------------------------------------------------
def require_role(min_role: str):
    """
    Enforces that the caller has an authenticated JWT with at least `min_role` in the role hierarchy.
    Viewer < Analyst < Operator < Admin.
    Also verifies granular permissions if configured for the user account.
    Rejects:
    - Missing, invalid, expired, or tampered tokens -> 401 Unauthorized
    - Missing or unknown role claim -> 403 Forbidden
    - Insufficient role level in hierarchy -> 403 Forbidden
    - Missing granular operational permission -> 403 Forbidden
    """
    if min_role not in ROLE_HIERARCHY:
        raise ValueError(f"Unknown required role: '{min_role}'")

    async def _role_dependency(
        request: Request,
        user: Dict[str, Any] = Depends(require_user_token)
    ) -> Dict[str, Any]:
        username = user.get("username", "anonymous")
        token_claims = user.get("token_claims", {})
        # Inspect role claim from verified token (fallback to user store if needed)
        role = token_claims.get("role") or user.get("role")

        if not role or role not in ROLE_HIERARCHY:
            log_access_denied(username, str(role), request.url.path, "Missing or unknown role claim")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Missing or unknown role claim ('{role}'). Valid roles: {ALL_ROLES}."
            )

        user_level = ROLE_HIERARCHY[role]
        required_level = ROLE_HIERARCHY[min_role]

        if user_level < required_level:
            log_access_denied(
                username, role, request.url.path,
                f"Insufficient privileges. Required '{min_role}', had '{role}'"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Insufficient privileges. Required role: '{min_role}', your role: '{role}'."
            )

        # Granular permission check: verify account holds required operational capability
        req_perm = ROUTE_PERMISSION_MAP.get(request.url.path)
        if req_perm and role != ROLE_ADMIN:
            user_perms = token_claims.get("permissions") or user.get("permissions") or []
            if "*" not in user_perms and req_perm not in user_perms:
                log_access_denied(
                    username, role, request.url.path,
                    f"Account lacks required operational permission '{req_perm}' (configured permissions: {user_perms})"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Forbidden: Account '{username}' lacks operational permission '{req_perm}'. Contact an Administrator."
                )

        if role == ROLE_ADMIN:
            log_admin_action(username, request.url.path, request.method)

        return user

    # Tag function for route reflection in tests
    _role_dependency.__cosmos_auth__ = "role"
    _role_dependency.__cosmos_role__ = min_role
    return _role_dependency


# ---------------------------------------------------------------------------
# 5. DEPENDENCY: require_service_key()
# ---------------------------------------------------------------------------
async def require_service_key(
    request: Request,
    x_service_key: Optional[str] = Header(None, alias=SERVICE_KEY_HEADER)
) -> Dict[str, Any]:
    """
    Strictly verifies inter-service X-Service-Key header using constant-time comparison.
    A service key is not a role and cannot act as a user.
    User tokens cannot call service-key routes.
    """
    if not x_service_key:
        log_access_denied("service_caller", "none", request.url.path, "Missing X-Service-Key header")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Missing required inter-service authentication header '{SERVICE_KEY_HEADER}'."
        )

    if not hmac.compare_digest(x_service_key.strip(), COSMOS_SERVICE_KEY.strip()):
        log_access_denied("service_caller", "invalid", request.url.path, "Invalid X-Service-Key")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Invalid '{SERVICE_KEY_HEADER}' presented."
        )

    return {
        "auth_type": "service",
        "identity": "cosmos_internal_service"
    }

require_service_key.__cosmos_auth__ = "service_key"


# ---------------------------------------------------------------------------
# 6. DEPENDENCY: require_service_key_or_admin()
# ---------------------------------------------------------------------------
async def require_service_key_or_admin(
    request: Request,
    x_service_key: Optional[str] = Header(None, alias=SERVICE_KEY_HEADER),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme)
) -> Dict[str, Any]:
    """
    Accepts EITHER:
    1. A valid X-Service-Key header, OR
    2. An authenticated user token with 'admin' role.
    All other callers are denied (401 if missing auth, 403 if insufficient).
    """
    # 1. Check Service Key first
    if x_service_key:
        if hmac.compare_digest(x_service_key.strip(), COSMOS_SERVICE_KEY.strip()):
            return {
                "auth_type": "service",
                "identity": "cosmos_internal_service"
            }
        else:
            log_access_denied("service_caller", "invalid", request.url.path, "Invalid X-Service-Key")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Invalid '{SERVICE_KEY_HEADER}' presented."
            )

    # 2. Check User Bearer Token for Admin role
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
        role = payload.get("role") or user.get("role")
        if role != ROLE_ADMIN:
            log_access_denied(username, str(role), request.url.path, "Admin role required for webhook/push")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Forbidden: Administrative privileges or internal service key required."
            )
        log_admin_action(username, request.url.path, request.method)
        return {
            "auth_type": "user",
            "identity": username,
            "role": ROLE_ADMIN,
            "user": user
        }

    # 3. Neither provided -> 401 Unauthorized
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=f"Authentication required: Provide a valid Admin JWT Bearer token or inter-service '{SERVICE_KEY_HEADER}' header.",
        headers={"WWW-Authenticate": "Bearer"},
    )

require_service_key_or_admin.__cosmos_auth__ = "service_key_or_admin"


# ---------------------------------------------------------------------------
# 7. DEPENDENCY: require_viewer_or_service_key()
# ---------------------------------------------------------------------------
async def require_viewer_or_service_key(
    request: Request,
    x_service_key: Optional[str] = Header(None, alias=SERVICE_KEY_HEADER),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme)
) -> Dict[str, Any]:
    """
    Accepts EITHER:
    1. A valid X-Service-Key header (used by DataManager and client_ingest), OR
    2. An authenticated user token with at least 'viewer' role.
    """
    # 1. Service Key
    if x_service_key:
        if hmac.compare_digest(x_service_key.strip(), COSMOS_SERVICE_KEY.strip()):
            return {
                "auth_type": "service",
                "identity": "cosmos_internal_service"
            }
        else:
            log_access_denied("service_caller", "invalid", request.url.path, "Invalid X-Service-Key on telemetry endpoint")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Invalid '{SERVICE_KEY_HEADER}' presented."
            )

    # 2. User Bearer Token (must be >= viewer)
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
        role = payload.get("role") or user.get("role")
        if not role or role not in ROLE_HIERARCHY:
            log_access_denied(username, str(role), request.url.path, "Missing or unknown role claim")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Forbidden: Missing or unknown role claim ('{role}')."
            )
        return {
            "auth_type": "user",
            "identity": username,
            "role": role,
            "user": user
        }

    # 3. Neither provided -> 401
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=f"Authentication required: Provide a valid JWT Bearer token or inter-service '{SERVICE_KEY_HEADER}' header.",
        headers={"WWW-Authenticate": "Bearer"},
    )

require_viewer_or_service_key.__cosmos_auth__ = "viewer_or_service_key"


def require_role_or_service_key(min_role: str):
    """
    Accepts EITHER:
    1. A valid X-Service-Key header (used for inter-service calls like MI -> DT), OR
    2. An authenticated user token with at least `min_role` in the role hierarchy.
    """
    if min_role not in ROLE_HIERARCHY:
        raise ValueError(f"Unknown required role: '{min_role}'")

    async def _role_or_service_checker(
        request: Request,
        x_service_key: Optional[str] = Header(None, alias=SERVICE_KEY_HEADER),
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme)
    ) -> Dict[str, Any]:
        # 1. Service Key check (constant-time)
        if x_service_key:
            if hmac.compare_digest(x_service_key.strip(), COSMOS_SERVICE_KEY.strip()):
                return {
                    "auth_type": "service",
                    "identity": "cosmos_internal_service"
                }
            log_access_denied("service_caller", "invalid", request.url.path, "Invalid X-Service-Key")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Invalid '{SERVICE_KEY_HEADER}' presented."
            )

        # 2. User Bearer Token check
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
            role = payload.get("role") or user.get("role")
            if not role or role not in ROLE_HIERARCHY:
                log_access_denied(username, str(role), request.url.path, "Missing or unknown role claim")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Forbidden: Missing or unknown role claim ('{role}')."
                )

            user_level = ROLE_HIERARCHY[role]
            required_level = ROLE_HIERARCHY[min_role]
            if user_level < required_level:
                log_access_denied(
                    username, role, request.url.path,
                    f"Insufficient privileges. Required '{min_role}', had '{role}'"
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Forbidden: Insufficient privileges. Required role: '{min_role}', your role: '{role}'."
                )

            # Granular permission check: verify account holds required operational capability
            req_perm = ROUTE_PERMISSION_MAP.get(request.url.path)
            if req_perm and role != ROLE_ADMIN:
                user_perms = payload.get("permissions") or user.get("permissions") or []
                if "*" not in user_perms and req_perm not in user_perms:
                    log_access_denied(
                        username, role, request.url.path,
                        f"Account lacks required operational permission '{req_perm}' (configured permissions: {user_perms})"
                    )
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Forbidden: Account '{username}' lacks operational permission '{req_perm}'. Contact an Administrator."
                    )

            if role == ROLE_ADMIN:
                log_admin_action(username, request.url.path, request.method)

            return user

        # 3. Neither provided -> 401
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication required: Provide a valid JWT Bearer token or inter-service '{SERVICE_KEY_HEADER}' header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    _role_or_service_checker.__cosmos_auth__ = "role_or_service_key"
    _role_or_service_checker.__cosmos_role__ = min_role
    return _role_or_service_checker


# ---------------------------------------------------------------------------
# 8. WEBSOCKET AUTHENTICATION HELPER
# ---------------------------------------------------------------------------
async def authenticate_websocket(websocket: WebSocket, min_role: str = ROLE_VIEWER) -> Optional[Dict[str, Any]]:
    """
    Authenticates a WebSocket connection using:
    1. Sec-WebSocket-Protocol header containing token, or
    2. Authorization header, or
    3. First message: {"type": "auth", "token": "<jwt>"}
    Never allows token in URL query parameters.
    Returns decoded token payload if valid and role >= min_role; otherwise closes with 1008 and returns None.
    """
    token = None
    selected_subprotocol = None

    # Check Sec-WebSocket-Protocol header
    protocols = websocket.headers.get("sec-websocket-protocol")
    if protocols:
        for proto in [p.strip() for p in protocols.split(",")]:
            if proto.lower().startswith("token."):
                token = proto[6:].strip()
                selected_subprotocol = proto
                break
            elif proto.lower().startswith("bearer."):
                token = proto[7:].strip()
                selected_subprotocol = proto
                break
            elif proto and proto.lower() not in ["bearer", "access_token", "jwt"]:
                token = proto
                selected_subprotocol = proto
                break

    # Check Authorization header if present
    if not token and "authorization" in websocket.headers:
        auth_hdr = websocket.headers["authorization"]
        if auth_hdr.lower().startswith("bearer "):
            token = auth_hdr[7:].strip()

    # If header not present, accept connection and wait for first auth message
    if not token:
        await websocket.accept()
        try:
            import asyncio
            auth_msg = await asyncio.wait_for(websocket.receive_json(), timeout=5.0)
            if isinstance(auth_msg, dict) and auth_msg.get("type") == "auth":
                token = auth_msg.get("token")
        except Exception:
            await websocket.close(code=1008, reason="Authentication timeout or invalid auth message")
            return None
    else:
        await websocket.accept(subprotocol=selected_subprotocol)

    if not token:
        await websocket.close(code=1008, reason="Authentication token missing")
        return None

    try:
        payload = verify_access_token(token)
        role = payload.get("role")
        if not role or role not in ROLE_HIERARCHY:
            await websocket.close(code=1008, reason="Missing or unknown role claim")
            return None
        
        user_level = ROLE_HIERARCHY[role]
        required_level = ROLE_HIERARCHY.get(min_role, 1)
        if user_level < required_level:
            await websocket.close(code=1008, reason="Insufficient privileges")
            return None
            
        return payload
    except HTTPException as e:
        await websocket.close(code=1008, reason=e.detail)
        return None
    except Exception:
        await websocket.close(code=1008, reason="Invalid token")
        return None
