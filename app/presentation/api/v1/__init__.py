"""API v1 root router."""

from fastapi import APIRouter

from app.presentation.api.v1 import auth, bookings, public
from app.presentation.api.v1.admin import admin_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(auth.admin_router)
api_router.include_router(bookings.router)
api_router.include_router(public.router)
api_router.include_router(admin_router)
