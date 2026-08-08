"""Unit coverage for online payment enable/disable gate on booking create."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.booking_creation import (
    _ensure_online_payment_enabled,
    create_booking,
)
from app.services.booking_shared import BookingError

pytestmark = pytest.mark.asyncio


def _db_returning_profile(profile) -> AsyncMock:
    result = MagicMock()
    result.scalar_one_or_none.return_value = profile
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    return db


async def test_ensure_online_payment_enabled_ok() -> None:
    db = _db_returning_profile(SimpleNamespace(online_payment_enabled=True))
    await _ensure_online_payment_enabled(db)


async def test_ensure_online_payment_disabled_raises() -> None:
    db = _db_returning_profile(SimpleNamespace(online_payment_enabled=False))
    with pytest.raises(BookingError, match="Online payment is disabled"):
        await _ensure_online_payment_enabled(db)


async def test_ensure_online_payment_missing_profile_raises() -> None:
    db = _db_returning_profile(None)
    with pytest.raises(BookingError, match="Online payment is disabled"):
        await _ensure_online_payment_enabled(db)


async def test_create_booking_rejects_online_when_disabled() -> None:
    db = _db_returning_profile(SimpleNamespace(online_payment_enabled=False))
    with pytest.raises(BookingError, match="Online payment is disabled"):
        await create_booking(
            db,
            trip_id=1,
            booking_date=__import__("datetime").date(2026, 8, 8),
            quantity=1,
            customer_name="A",
            customer_phone="0900000000",
            customer_email="a@example.com",
            dropoff_stop_id=1,
            total_price=100000,
            payment_method="online_banking",
        )
