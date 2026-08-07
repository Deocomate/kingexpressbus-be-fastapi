"""Password hashing (bcrypt, including $2y$ prefix) and JWT helpers."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import get_settings


def hash_password(plain: str) -> str:
    raw = bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt(rounds=12))
    # Prefer $2y$ prefix for stored hashes; bcrypt lib emits $2b$
    return raw.decode("utf-8").replace("$2b$", "$2y$", 1)


def verify_password(plain: str, hashed: str | None) -> bool:
    if not plain or not hashed or not isinstance(hashed, str):
        return False
    if not (
        hashed.startswith("$2y$")
        or hashed.startswith("$2b$")
        or hashed.startswith("$2a$")
    ):
        return False
    normalized = hashed.replace("$2y$", "$2b$", 1)
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), normalized.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(user_id: int, role: str) -> str:
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> dict[str, Any] | None:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[settings.jwt_algorithm],
        )
    except jwt.PyJWTError:
        return None
