"""Password hashing (bcrypt, including $2y$ prefix) and JWT helpers.

Compatibility shim — implementation lives in infrastructure.security.
"""

from app.infrastructure.security.passwords_jwt import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

__all__ = [
    "create_access_token",
    "decode_access_token",
    "hash_password",
    "verify_password",
]
