"""Shared types/constants for booking use cases."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal

from app.domain.booking.errors import BookingError
from app.domain.shared.errors import PriceChangedError
from app.infrastructure.persistence.models import Booking

COUNTED_STATUSES = ("pending", "confirmed", "completed")
ALL_STATUSES = ("pending", "confirmed", "completed", "cancelled")
EmailAction = Literal["confirmation", "payment_request", "approval", "cancellation"] | None

__all__ = [
    "ALL_STATUSES",
    "Booking",
    "BookingError",
    "BookingResult",
    "COUNTED_STATUSES",
    "EmailAction",
    "PriceChangedError",
    "_utcnow",
]


@dataclass
class BookingResult:
    booking: Booking
    email_action: EmailAction = None
    cancel_reason: str | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
