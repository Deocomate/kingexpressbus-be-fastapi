"""Booking-specific domain errors."""

from __future__ import annotations

from app.domain.shared.errors import DomainError


class BookingError(DomainError):
    """Booking use-case failure (availability, validation, business rules)."""
