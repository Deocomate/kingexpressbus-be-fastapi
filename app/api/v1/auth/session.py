"""Auth session: login, register, logout, me + admin login."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select

from app.core.deps import (
    AppSettings,
    DbSession,
    get_current_user_optional,
    require_same_origin,
)
from app.core.rate_limit import client_ip, rate_limiter
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.models import User
from app.schemas.auth import (
    LoginRequest,
    MessageOut,
    RegisterRequest,
    UserOut,
)

router = APIRouter(prefix="/auth", tags=["auth"])
admin_router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])


def _set_session_cookie(response: Response, token: str, settings: AppSettings) -> None:
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
        max_age=settings.jwt_expire_minutes * 60,
        path="/",
    )


def _clear_session_cookie(response: Response, settings: AppSettings) -> None:
    response.delete_cookie(key=settings.cookie_name, path="/")


@router.post("/login", response_model=UserOut, dependencies=[Depends(require_same_origin)])
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
) -> User:
    rate_limiter.hit(f"auth:login:ip:{client_ip(request)}", limit=5)

    result = await db.execute(select(User).where(User.email == body.email.lower()))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    token = create_access_token(user.id, user.role)
    _set_session_cookie(response, token, settings)
    return user


@admin_router.post(
    "/login",
    response_model=UserOut,
    dependencies=[Depends(require_same_origin)],
)
async def admin_login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
) -> User:
    ip = client_ip(request)
    rate_limiter.hit(f"admin:login:ip:{ip}", limit=20)
    rate_limiter.hit(
        f"admin:login:combo:{ip}|{body.email.lower()}",
        limit=5,
    )

    result = await db.execute(select(User).where(User.email == body.email.lower()))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(body.password, user.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin role required",
        )
    token = create_access_token(user.id, user.role)
    _set_session_cookie(response, token, settings)
    return user


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_same_origin)],
)
async def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
) -> User:
    rate_limiter.hit(f"auth:register:ip:{client_ip(request)}", limit=5)

    email = body.email.lower()
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Email already registered",
        )

    user = User(
        name=body.name,
        email=email,
        phone=body.phone,
        password=hash_password(body.password),
        role="customer",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id, user.role)
    _set_session_cookie(response, token, settings)
    return user


@router.post("/logout", response_model=MessageOut, dependencies=[Depends(require_same_origin)])
async def logout(response: Response, settings: AppSettings) -> MessageOut:
    _clear_session_cookie(response, settings)
    return MessageOut(message="Logged out")


@router.get("/me", response_model=UserOut | None)
async def me(
    user: Annotated[User | None, Depends(get_current_user_optional)],
) -> User | None:
    """Guest-safe session probe: 200 + null when no cookie / invalid session."""
    return user
