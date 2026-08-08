"""Admin booking query/write/status-action endpoints (aggregated router)."""

from __future__ import annotations

from fastapi import APIRouter

from app.presentation.api.v1.admin.bookings import (
    bookings_actions,
    bookings_query,
    bookings_write,
)

router = APIRouter()
router.include_router(bookings_query.router)
router.include_router(bookings_write.router)
router.include_router(bookings_actions.router)
