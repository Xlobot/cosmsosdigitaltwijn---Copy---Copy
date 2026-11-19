"""
COSMOS Shared Security Configuration
====================================
Loads security parameters from environment variables / .env file.
Fails fast on startup if critical secrets (JWT_SECRET_KEY, COSMOS_SERVICE_KEY) are missing.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Search for .env starting from current file directory up to 3 levels
_current_dir = Path(__file__).resolve().parent
_candidates = [
    _current_dir / ".env",
    _current_dir.parent / ".env",
    Path.cwd() / ".env"
]

for env_path in _candidates:
    if env_path.is_file():
        load_dotenv(dotenv_path=env_path)
        break
else:
    load_dotenv()

# Required Secrets - Fail fast if missing
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not JWT_SECRET_KEY or not JWT_SECRET_KEY.strip():
    raise RuntimeError(
        "CRITICAL SECURITY CONFIG ERROR: 'JWT_SECRET_KEY' environment variable is missing or empty. "
        "Set JWT_SECRET_KEY in your environment or .env file (refer to .env.example). "
        "Service halted."
    )

COSMOS_SERVICE_KEY = os.getenv("COSMOS_SERVICE_KEY")
if not COSMOS_SERVICE_KEY or not COSMOS_SERVICE_KEY.strip():
    raise RuntimeError(
        "CRITICAL SECURITY CONFIG ERROR: 'COSMOS_SERVICE_KEY' environment variable is missing or empty. "
        "Set COSMOS_SERVICE_KEY in your environment or .env file (refer to .env.example). "
        "Service halted."
    )

# Operational Security Parameters
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRATION_MINUTES = int(os.getenv("JWT_EXPIRATION_MINUTES", "15"))  # 15 min expiry per spec
SERVICE_KEY_HEADER = "X-Service-Key"

# Default Admin Credentials for Seeding
COSMOS_ADMIN_USERNAME = os.getenv("COSMOS_ADMIN_USERNAME", "admin").strip()
COSMOS_ADMIN_PASSWORD = os.getenv("COSMOS_ADMIN_PASSWORD", "CosmosFlightOps2026!").strip()
if not COSMOS_ADMIN_PASSWORD:
    raise RuntimeError(
        "CRITICAL SECURITY CONFIG ERROR: 'COSMOS_ADMIN_PASSWORD' environment variable cannot be empty."
    )

# Database Storage for User Credentials
_default_db_path = str(_current_dir.parent / "cosmos_users.db")
COSMOS_DB_PATH = os.getenv("COSMOS_DB_PATH", _default_db_path)
