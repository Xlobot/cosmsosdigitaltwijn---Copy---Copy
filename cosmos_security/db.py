"""
COSMOS Shared User Storage Engine (SQLite)
==========================================
Manages user accounts, Argon2 password hashes, user roles, and granular permissions in SQLite.
Enforces Role-Based Access Control (RBAC):
- Administrator: Full unrestricted access to all flight operations + exclusively adds/manages users & permissions.
- Flight Operator: Configurable operational permissions (telemetry, predictions, scenario branching, fault injection, decision uplink).
"""

import sqlite3
import os
import json
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from .config import COSMOS_DB_PATH, COSMOS_ADMIN_USERNAME, COSMOS_ADMIN_PASSWORD
from .passwords import hash_password, verify_password

ALL_PERMISSIONS = [
    "telemetry:read",      # View live & historical telemetry, replay slider
    "predict:run",         # Run forward orbital propagations
    "scenarios:fork",      # Branch into candidate maneuvers & what-if branches
    "anomalies:inject",    # Inject synthetic telemetry faults
    "mission_intel:assess",# Request cognitive situation assessment
    "mission_intel:decide",# Submit accept/reject decisions to uplink
    "users:manage"         # Exclusively for administrators
]

DEFAULT_OPERATOR_PERMS = [
    "telemetry:read",
    "predict:run",
    "scenarios:fork",
    "mission_intel:assess",
    "mission_intel:decide"
]


def get_db_connection() -> sqlite3.Connection:
    """Open a thread-safe connection to the SQLite database."""
    os.makedirs(os.path.dirname(os.path.abspath(COSMOS_DB_PATH)), exist_ok=True)
    conn = sqlite3.connect(COSMOS_DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Create the users table if it does not already exist, and migrate columns."""
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL COLLATE NOCASE,
                    hashed_password TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'operator',
                    permissions TEXT NOT NULL DEFAULT '["telemetry:read"]',
                    created_at TEXT NOT NULL,
                    last_login TEXT
                );
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);")

            # Schema migration: check if 'permissions' column exists
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(users);")
            cols = [row["name"] for row in cursor.fetchall()]
            if "permissions" not in cols:
                conn.execute("ALTER TABLE users ADD COLUMN permissions TEXT NOT NULL DEFAULT '[\"telemetry:read\"]';")
    finally:
        conn.close()


def _format_user_row(row: Optional[sqlite3.Row], include_hash: bool = False) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    d = dict(row)
    # Parse permissions JSON string into list
    raw_perms = d.get("permissions")
    if isinstance(raw_perms, str):
        try:
            d["permissions"] = json.loads(raw_perms)
        except Exception:
            d["permissions"] = ["*"] if d.get("role") == "admin" else ["telemetry:read"]
    elif not isinstance(raw_perms, list):
        d["permissions"] = ["*"] if d.get("role") == "admin" else ["telemetry:read"]

    if not include_hash and "hashed_password" in d:
        del d["hashed_password"]
    return d


def get_user_by_username(username: str, include_hash: bool = True) -> Optional[Dict[str, Any]]:
    """Retrieve a user record by username."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username.strip(),))
        row = cursor.fetchone()
        return _format_user_row(row, include_hash=include_hash)
    finally:
        conn.close()


def get_all_users() -> List[Dict[str, Any]]:
    """Retrieve all user accounts (excluding password hashes) for admin management."""
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, role, permissions, created_at, last_login FROM users ORDER BY id ASC")
        rows = cursor.fetchall()
        return [_format_user_row(r, include_hash=False) for r in rows]
    finally:
        conn.close()


def create_user(
    username: str,
    plain_password: str,
    role: str = "operator",
    permissions: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Create a new user with an Argon2 hashed password and specific permissions."""
    clean_username = username.strip()
    if not clean_username:
        raise ValueError("Username cannot be empty.")
    if len(plain_password) < 6:
        raise ValueError("Password must be at least 6 characters long.")

    hashed = hash_password(plain_password)
    now_str = datetime.now(timezone.utc).isoformat()

    if permissions is None:
        if role == "admin":
            perms_list = ["*"]
        else:
            perms_list = list(DEFAULT_OPERATOR_PERMS)
    else:
        perms_list = list(permissions)
        if role == "admin" and "*" not in perms_list:
            perms_list.append("*")

    perms_json = json.dumps(perms_list)

    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO users (username, hashed_password, role, permissions, created_at) VALUES (?, ?, ?, ?, ?)",
                (clean_username, hashed, role, perms_json, now_str)
            )
            user_id = cursor.lastrowid
        return {
            "id": user_id,
            "username": clean_username,
            "role": role,
            "permissions": perms_list,
            "created_at": now_str
        }
    finally:
        conn.close()


def update_user_permissions(
    username: str,
    role: Optional[str] = None,
    permissions: Optional[List[str]] = None
) -> Dict[str, Any]:
    """Update role and permissions of an existing user (Admin only)."""
    clean_username = username.strip()
    user = get_user_by_username(clean_username, include_hash=False)
    if not user:
        raise ValueError(f"User '{clean_username}' not found.")

    new_role = role if role is not None else user["role"]
    
    if permissions is not None:
        new_perms = list(permissions)
        if new_role == "admin" and "*" not in new_perms:
            new_perms.append("*")
    else:
        new_perms = user.get("permissions", ["telemetry:read"])

    perms_json = json.dumps(new_perms)

    conn = get_db_connection()
    try:
        with conn:
            conn.execute(
                "UPDATE users SET role = ?, permissions = ? WHERE username = ?",
                (new_role, perms_json, clean_username)
            )
        return {
            "username": clean_username,
            "role": new_role,
            "permissions": new_perms
        }
    finally:
        conn.close()


def delete_user(username: str) -> bool:
    """Delete a user account from SQLite."""
    clean_username = username.strip()
    if clean_username.lower() == COSMOS_ADMIN_USERNAME.lower():
        raise ValueError("Cannot delete the root administrative account.")
    conn = get_db_connection()
    try:
        with conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE username = ?", (clean_username,))
            return cursor.rowcount > 0
    finally:
        conn.close()


def update_user_last_login(username: str):
    """Record last login timestamp for audit purposes."""
    now_str = datetime.now(timezone.utc).isoformat()
    conn = get_db_connection()
    try:
        with conn:
            conn.execute("UPDATE users SET last_login = ? WHERE username = ?", (now_str, username.strip()))
    finally:
        conn.close()


def seed_admin_user():
    """
    Ensure an administrative account exists per environment variables.
    Admin has full access to everything (permissions = ["*"]).
    """
    init_db()
    admin_user = get_user_by_username(COSMOS_ADMIN_USERNAME, include_hash=True)
    admin_perms_json = json.dumps(["*"])

    if not admin_user:
        hashed = hash_password(COSMOS_ADMIN_PASSWORD)
        now_str = datetime.now(timezone.utc).isoformat()
        conn = get_db_connection()
        try:
            with conn:
                conn.execute(
                    "INSERT INTO users (username, hashed_password, role, permissions, created_at) VALUES (?, ?, ?, ?, ?)",
                    (COSMOS_ADMIN_USERNAME, hashed, "admin", admin_perms_json, now_str)
                )
            print(f"[COSMOS Security] Seeded root administrator: '{COSMOS_ADMIN_USERNAME}' with full permissions ['*']")
        finally:
            conn.close()
    else:
        # Update admin permissions to full access and sync password hash if changed
        conn = get_db_connection()
        try:
            with conn:
                if not verify_password(COSMOS_ADMIN_PASSWORD, admin_user["hashed_password"]):
                    new_hash = hash_password(COSMOS_ADMIN_PASSWORD)
                    conn.execute(
                        "UPDATE users SET hashed_password = ?, role = 'admin', permissions = ? WHERE username = ?",
                        (new_hash, admin_perms_json, COSMOS_ADMIN_USERNAME)
                    )
                    print(f"[COSMOS Security] Synced administrator '{COSMOS_ADMIN_USERNAME}' password hash and permissions.")
                else:
                    conn.execute(
                        "UPDATE users SET role = 'admin', permissions = ? WHERE username = ?",
                        (admin_perms_json, COSMOS_ADMIN_USERNAME)
                    )
        finally:
            conn.close()
