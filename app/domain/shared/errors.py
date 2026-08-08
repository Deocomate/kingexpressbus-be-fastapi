"""Domain-level errors (presentation maps these to HTTP)."""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Base domain failure with optional HTTP status hint."""

    def __init__(self, message: str, *, status_code: int = 422) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class NotFoundError(DomainError):
    def __init__(self, message: str = "Not found") -> None:
        super().__init__(message, status_code=404)


class PriceChangedError(DomainError):
    """Submitted booking total no longer matches server pricing."""

    def __init__(
        self,
        submitted_total: int,
        breakdown: dict[str, Any],
        server_total: int,
    ) -> None:
        super().__init__("price_changed", status_code=409)
        self.submitted_total = submitted_total
        self.breakdown = breakdown
        self.server_total = server_total
