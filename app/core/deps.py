"""FastAPI dependencies: DB session, auth, CSRF/origin checks."""

from collections.abc import Callable
from typing import Annotated
from urllib.parse import urlparse

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.security import decode_access_token
from app.db.models import User
from app.db.session import get_db

DbSession = Annotated[AsyncSession, Depends(get_db)]
AppSettings = Annotated[Settings, Depends(get_settings)]


def _origin_allowed(origin_or_referer: str | None, allowlist: list[str]) -> bool:
    if "*" in allowlist:
        return True
    if not origin_or_referer:
        return False
    parsed = urlparse(origin_or_referer)
    origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme else origin_or_referer
    return origin in allowlist


async def require_same_origin(
    request: Request,
    settings: AppSettings,
) -> None:
    """Reject cross-site cookie mutations without a matching Origin/Referer.

    Skipped when CORS_ORIGINS includes ``*``.
    """
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    if settings.cors_allows_all:
        return
    allowlist = settings.cors_origin_list
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    if _origin_allowed(origin, allowlist) or _origin_allowed(referer, allowlist):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Origin not allowed",
    )


async def get_current_user_optional(
    request: Request,
    db: DbSession,
    settings: AppSettings,
) -> User | None:
    token = request.cookies.get(settings.cookie_name)
    if not token:
        return None
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        return None
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError):
        return None
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_current_user(
    user: Annotated[User | None, Depends(get_current_user_optional)],
) -> User:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


def require_role(*roles: str) -> Callable:
    async def _dep(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role",
            )
        return user

    return _dep


require_admin = require_role("admin")
require_customer = require_role("customer", "admin")
