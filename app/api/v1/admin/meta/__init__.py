"""Admin options search + uploads + dashboard stats (aggregated router)."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.admin.meta import meta_dashboard, meta_options, meta_uploads

router = APIRouter()
router.include_router(meta_options.router)
router.include_router(meta_uploads.router)
router.include_router(meta_dashboard.router)
