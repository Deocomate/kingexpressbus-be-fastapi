"""Shared constants for hotel/tour bookings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from app.domain.booking.errors import BookingError

COUNTED_STATUSES = ("pending", "confirmed", "completed")
ALL_STATUSES = ("pending", "confirmed", "completed", "cancelled")
PAYMENT_METHODS = ("cash_at_property", "bank_transfer")
EmailAction = Literal["confirmation", "approval", "cancellation"] | None


@dataclass
class ServiceBookingResult:
    booking: object
    email_action: EmailAction = None
    cancel_reason: str | None = None


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


__all__ = [
    "ALL_STATUSES",
    "BookingError",
    "COUNTED_STATUSES",
    "EmailAction",
    "PAYMENT_METHODS",
    "ServiceBookingResult",
    "utcnow",
]
