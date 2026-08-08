"""Public booking + payment endpoints (aggregated router)."""

from __future__ import annotations

from fastapi import APIRouter

from app.presentation.api.v1.bookings import booking_routes, payment_routes

router = APIRouter()
router.include_router(booking_routes.router)
router.include_router(payment_routes.router)
