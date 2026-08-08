"""Admin CRUD: provinces, district-types, districts, stops (aggregated router)."""

from __future__ import annotations

from fastapi import APIRouter

from app.presentation.api.v1.admin.locations import (
    district_types,
    districts,
    provinces,
    stops,
)

router = APIRouter()
router.include_router(provinces.router)
router.include_router(district_types.router)
router.include_router(districts.router)
router.include_router(stops.router)
