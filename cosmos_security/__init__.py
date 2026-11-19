"""
COSMOS Shared Security & Authentication Package
===============================================
Unified security architecture for Digital Twin, Mission Intelligence, and Telemetry Generator.
Provides:
- Argon2id password hashing via pwdlib
- JWT token issuing & validation with 15-minute expiry via PyJWT
- SQLite user persistence & automated admin seeding
- Centralized Role-Based Access Control (RBAC): viewer < analyst < operator < admin
- Single central permission table across all three services
- Fail-fast environment variable validation
- Inter-service X-Service-Key authentication
"""

from .config import (
    JWT_SECRET_KEY,
    COSMOS_SERVICE_KEY,
    COSMOS_ADMIN_USERNAME,
    COSMOS_ADMIN_PASSWORD,
    COSMOS_DB_PATH,
    JWT_EXPIRATION_MINUTES,
    SERVICE_KEY_HEADER
)
from .passwords import hash_password, verify_password
from .tokens import create_access_token, verify_access_token
from .db import (
    init_db,
    get_user_by_username,
    get_all_users,
    create_user,
    update_user_permissions,
    delete_user,
    seed_admin_user,
    update_user_last_login,
    ALL_PERMISSIONS,
    DEFAULT_OPERATOR_PERMS
)
from .dependencies import (
    require_user_token,
    require_service_key,
    require_user_or_service_key,
    require_admin_role,
    require_permission,
    get_service_headers
)
from .authz import (
    ROLE_VIEWER,
    ROLE_ANALYST,
    ROLE_OPERATOR,
    ROLE_ADMIN,
    ALL_ROLES,
    ROLE_HIERARCHY,
    PERMISSION_TABLE,
    require_role,
    require_service_key as require_authz_service_key,
    require_service_key_or_admin,
    require_viewer_or_service_key,
    require_role_or_service_key,
    authenticate_websocket,
    log_access_denied,
    log_admin_action
)

__all__ = [
    "JWT_SECRET_KEY",
    "COSMOS_SERVICE_KEY",
    "COSMOS_ADMIN_USERNAME",
    "COSMOS_ADMIN_PASSWORD",
    "COSMOS_DB_PATH",
    "JWT_EXPIRATION_MINUTES",
    "SERVICE_KEY_HEADER",
    "hash_password",
    "verify_password",
    "create_access_token",
    "verify_access_token",
    "init_db",
    "get_user_by_username",
    "get_all_users",
    "create_user",
    "update_user_permissions",
    "delete_user",
    "seed_admin_user",
    "update_user_last_login",
    "ALL_PERMISSIONS",
    "DEFAULT_OPERATOR_PERMS",
    "require_user_token",
    "require_service_key",
    "require_user_or_service_key",
    "require_admin_role",
    "require_permission",
    "get_service_headers",
    "ROLE_VIEWER",
    "ROLE_ANALYST",
    "ROLE_OPERATOR",
    "ROLE_ADMIN",
    "ALL_ROLES",
    "ROLE_HIERARCHY",
    "PERMISSION_TABLE",
    "require_role",
    "require_authz_service_key",
    "require_service_key_or_admin",
    "require_viewer_or_service_key",
    "require_role_or_service_key",
    "authenticate_websocket",
    "log_access_denied",
    "log_admin_action"
]
