"""Guest checkout users and claim-on-register helpers.

Guest rows have password=null and typically role="guest". Register may claim
those rows by setting a password and promoting role to customer. Orphan
bookings (user_id null, same email) are attached after create/claim so the
account page shows prior guest tickets.
"""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.models import Booking, User


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def get_user_by_email(db: AsyncSession, email: str) -> User | None:
    result = await db.execute(
        select(User).where(User.email == normalize_email(email))
    )
    return result.scalar_one_or_none()


async def ensure_customer_user(
    db: AsyncSession,
    *,
    name: str,
    email: str,
    phone: str | None = None,
) -> User:
    """Find or create a user for guest checkout; never overwrite a real password."""
    email_norm = normalize_email(email)
    user = await get_user_by_email(db, email_norm)
    name_clean = name.strip()
    phone_clean = phone.strip() if phone and phone.strip() else None

    if user is None:
        user = User(
            name=name_clean,
            email=email_norm,
            phone=phone_clean,
            password=None,
            role="guest",
        )
        db.add(user)
        await db.flush()
        return user

    # Soft-refresh guest profile from the latest booking contact info.
    if user.password is None:
        if name_clean:
            user.name = name_clean
        if phone_clean:
            user.phone = phone_clean
        if user.role not in ("admin", "customer"):
            user.role = "guest"
        await db.flush()

    return user


async def claim_guest_user(
    db: AsyncSession,
    user: User,
    *,
    name: str,
    password: str,
    phone: str | None = None,
) -> User:
    """Promote a null-password guest into a customer with a login password."""
    if user.password is not None:
        raise ValueError("User already has a password")
    user.name = name.strip()
    user.password = hash_password(password)
    user.role = "customer"
    if phone is not None:
        phone_clean = phone.strip() if phone.strip() else None
        if phone_clean:
            user.phone = phone_clean
    await db.flush()
    return user


async def attach_orphan_bookings(
    db: AsyncSession,
    *,
    user_id: int,
    email: str,
) -> int:
    """Link bookings that used this email but have no user_id yet."""
    email_norm = normalize_email(email)
    result = await db.execute(
        update(Booking)
        .where(
            Booking.user_id.is_(None),
            func.lower(Booking.customer_email) == email_norm,
        )
        .values(user_id=user_id)
    )
    return int(result.rowcount or 0)
