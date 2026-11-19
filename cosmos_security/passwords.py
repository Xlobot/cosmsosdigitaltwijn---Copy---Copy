"""
COSMOS Shared Password Hashing Engine
=====================================
Uses pwdlib with Argon2id for secure password hashing and verification.
No plaintext passwords are ever persisted or compared directly.
"""

from pwdlib import PasswordHash

# Initialize PasswordHash with the recommended argon2id scheme
_password_hash = PasswordHash.recommended()


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    if not plain_password:
        raise ValueError("Password cannot be empty.")
    return _password_hash.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a stored Argon2 hash."""
    if not plain_password or not hashed_password:
        return False
    try:
        return _password_hash.verify(plain_password, hashed_password)
    except Exception:
        return False
