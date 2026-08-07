"""Shared types/constants for the booking service split (errors, result, clock helper)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from app.db.models import Booking

COUNTED_STATUSES = ("pending", "confirmed", "completed")
ALL_STATUSES = ("pending", "confirmed", "completed", "cancelled")
EmailAction = Literal["confirmation", "payment_request", "approval", "cancellation"] | None


class BookingError(Exception):
    def __init__(self, message: str, *, status_code: int = 422) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class PriceChangedError(Exception):
    def __init__(self, submitted_total: int, breakdown: dict[str, Any], server_total: int) -> None:
        super().__init__("price_changed")
        self.submitted_total = submitted_total
        self.breakdown = breakdown
        self.server_total = server_total


@dataclass
class BookingResult:
    booking: Booking
    email_action: EmailAction = None
    cancel_reason: str | None = None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
