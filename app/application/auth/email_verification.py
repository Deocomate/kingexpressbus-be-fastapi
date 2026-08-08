"""4-digit email verification OTP for signup / guest claim."""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import hash_password, verify_password
from app.infrastructure.mail.mail_sender import get_mail_sender
from app.infrastructure.persistence.models import EmailVerificationToken, User

logger = logging.getLogger(__name__)

CODE_TTL_MINUTES = 15


def generate_code() -> str:
    return f"{secrets.randbelow(10000):04d}"


def _utcnow_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


async def issue_verification_code(
    db: AsyncSession,
    *,
    email: str,
    settings: Settings,
    name: str | None = None,
) -> str:
    """Store a hashed 4-digit code and send it by email. Returns the plaintext code."""
    email_norm = email.strip().lower()
    code = generate_code()
    token_hash = hash_password(code)
    now = _utcnow_naive()

    existing = await db.get(EmailVerificationToken, email_norm)
    if existing:
        existing.token = token_hash
        existing.created_at = now
    else:
        db.add(
            EmailVerificationToken(
                email=email_norm,
                token=token_hash,
                created_at=now,
            )
        )
    await db.flush()

    display_name = (name or "").strip() or email_norm
    subject = "Mã xác thực tài khoản King Express Bus"
    html = (
        f"<p>Xin chào {display_name},</p>"
        f"<p>Mã xác thực của bạn là:</p>"
        f'<p style="font-size:28px;font-weight:700;letter-spacing:6px">{code}</p>'
        f"<p>Mã có hiệu lực trong {CODE_TTL_MINUTES} phút.</p>"
        f"<p>Nếu bạn không yêu cầu mã này, hãy bỏ qua email.</p>"
    )
    try:
        await get_mail_sender(settings).send(
            to=[email_norm],
            subject=subject,
            html=html,
        )
    except Exception:
        logger.exception("Failed to send verification email to %s", email_norm)
        # Still keep the token so resend / tests can proceed; SMTP may be unset locally.
        logger.info("Verification code issued for %s (mail may be skipped)", email_norm)

    return code


async def verify_code(
    db: AsyncSession,
    *,
    email: str,
    code: str,
) -> bool:
    email_norm = email.strip().lower()
    row = await db.get(EmailVerificationToken, email_norm)
    if row is None or not verify_password(code.strip(), row.token):
        return False
    if row.created_at is None or row.created_at < _utcnow_naive() - timedelta(
        minutes=CODE_TTL_MINUTES
    ):
        return False
    return True


async def consume_verification(
    db: AsyncSession,
    *,
    user: User,
    email: str,
) -> None:
    email_norm = email.strip().lower()
    user.email_verified_at = _utcnow_naive()
    row = await db.get(EmailVerificationToken, email_norm)
    if row is not None:
        await db.delete(row)
    await db.flush()


def is_email_verified(user: User) -> bool:
    return user.email_verified_at is not None
