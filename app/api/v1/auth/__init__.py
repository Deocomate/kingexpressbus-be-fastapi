"""Auth API: login, register, logout, me, password reset (aggregated router)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.auth import password_reset, session

router = APIRouter()
router.include_router(session.router)
router.include_router(password_reset.router)

admin_router = session.admin_router
