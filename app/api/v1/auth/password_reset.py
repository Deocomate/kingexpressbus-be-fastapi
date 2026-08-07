"""Auth: forgot-password / reset-password."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select

from app.core.deps import DbSession, require_same_origin
from app.core.rate_limit import client_ip, rate_limiter
from app.core.security import hash_password, verify_password
from app.db.models import PasswordResetToken, User
from app.schemas.auth import ForgotPasswordRequest, MessageOut, ResetPasswordRequest

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/forgot-password",
    response_model=MessageOut,
    dependencies=[Depends(require_same_origin)],
)
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    db: DbSession,
) -> MessageOut:
    rate_limiter.hit(f"auth:forgot:ip:{client_ip(request)}", limit=5)
    email = body.email.lower()
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    # Always return success to avoid account enumeration
    if user is not None:
        raw = secrets.token_urlsafe(32)
        token_hash = hash_password(raw)
        existing = await db.get(PasswordResetToken, email)
        if existing:
            existing.token = token_hash
            existing.created_at = datetime.now(UTC).replace(tzinfo=None)
        else:
            db.add(
                PasswordResetToken(
                    email=email,
                    token=token_hash,
                    created_at=datetime.now(UTC).replace(tzinfo=None),
                )
            )
        await db.commit()
        # Mail delivery lands in phase 4; raw token logged only in debug locally
    return MessageOut(message="If that email exists, a reset link was sent")


@router.post(
    "/reset-password",
    response_model=MessageOut,
    dependencies=[Depends(require_same_origin)],
)
async def reset_password(
    body: ResetPasswordRequest,
    request: Request,
    db: DbSession,
) -> MessageOut:
    rate_limiter.hit(f"auth:reset:ip:{client_ip(request)}", limit=5)
    email = body.email.lower()
    row = await db.get(PasswordResetToken, email)
    if row is None or not verify_password(body.token, row.token):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )
    if row.created_at is None or row.created_at < datetime.now(UTC).replace(
        tzinfo=None
    ) - timedelta(minutes=60):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )

    user.password = hash_password(body.password)
    await db.delete(row)
    await db.commit()
    return MessageOut(message="Password updated")
