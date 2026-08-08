"""Auth session: login, register, verify-email, logout, me + admin login."""

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
    RegisterPendingOut,
    RegisterRequest,
    ResendVerificationRequest,
    UserOut,
    VerifyEmailRequest,
)
from app.services import customer_accounts, email_verification

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
    # Must mirror set_cookie attrs (secure/samesite/httponly/path) or browsers
    # keep the session cookie — especially with SameSite=None; Secure.
    response.delete_cookie(
        key=settings.cookie_name,
        path="/",
        secure=settings.cookie_secure,
        httponly=True,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
    )


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
    if not email_verification.is_email_verified(user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified",
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
    response_model=RegisterPendingOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_same_origin)],
)
async def register(
    body: RegisterRequest,
    request: Request,
    db: DbSession,
    settings: AppSettings,
) -> RegisterPendingOut:
    rate_limiter.hit(f"auth:register:ip:{client_ip(request)}", limit=5)

    email = customer_accounts.normalize_email(str(body.email))
    existing = await customer_accounts.get_user_by_email(db, email)

    if existing is not None and existing.password is not None:
        if email_verification.is_email_verified(existing):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Email already registered",
            )
        # Unverified account re-registering: refresh profile + password, resend code.
        existing.name = body.name.strip()
        existing.password = hash_password(body.password)
        existing.role = "customer"
        if body.phone and body.phone.strip():
            existing.phone = body.phone.strip()
        existing.email_verified_at = None
        user = existing
    elif existing is not None and existing.password is None:
        user = await customer_accounts.claim_guest_user(
            db,
            existing,
            name=body.name,
            password=body.password,
            phone=body.phone,
        )
        user.email_verified_at = None
    else:
        user = User(
            name=body.name.strip(),
            email=email,
            phone=body.phone.strip() if body.phone and body.phone.strip() else None,
            password=hash_password(body.password),
            role="customer",
            email_verified_at=None,
        )
        db.add(user)
        await db.flush()

    await customer_accounts.attach_orphan_bookings(
        db, user_id=user.id, email=email
    )
    await email_verification.issue_verification_code(
        db,
        email=email,
        settings=settings,
        name=user.name,
    )
    await db.commit()

    return RegisterPendingOut(
        email=email,
        verification_required=True,
        message="Verification code sent",
    )


@router.post(
    "/verify-email",
    response_model=UserOut,
    dependencies=[Depends(require_same_origin)],
)
async def verify_email(
    body: VerifyEmailRequest,
    request: Request,
    response: Response,
    db: DbSession,
    settings: AppSettings,
) -> User:
    rate_limiter.hit(f"auth:verify:ip:{client_ip(request)}", limit=10)

    email = customer_accounts.normalize_email(str(body.email))
    user = await customer_accounts.get_user_by_email(db, email)
    if user is None or user.password is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code",
        )

    ok = await email_verification.verify_code(db, email=email, code=body.code)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code",
        )

    await email_verification.consume_verification(db, user=user, email=email)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id, user.role)
    _set_session_cookie(response, token, settings)
    return user


@router.post(
    "/resend-verification",
    response_model=MessageOut,
    dependencies=[Depends(require_same_origin)],
)
async def resend_verification(
    body: ResendVerificationRequest,
    request: Request,
    db: DbSession,
    settings: AppSettings,
) -> MessageOut:
    rate_limiter.hit(f"auth:resend-verify:ip:{client_ip(request)}", limit=5)

    email = customer_accounts.normalize_email(str(body.email))
    user = await customer_accounts.get_user_by_email(db, email)
    # Always succeed to avoid account enumeration.
    if (
        user is not None
        and user.password is not None
        and not email_verification.is_email_verified(user)
    ):
        await email_verification.issue_verification_code(
            db,
            email=email,
            settings=settings,
            name=user.name,
        )
        await db.commit()
    return MessageOut(message="If that email needs verification, a code was sent")


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
