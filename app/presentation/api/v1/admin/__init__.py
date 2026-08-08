"""Admin API router aggregate."""

from fastapi import APIRouter

from app.presentation.api.v1.admin import (
    bookings,
    fleet,
    hotels_admin,
    locations,
    meta,
    routes_admin,
    surcharges,
    tours_admin,
    trips_admin,
    website,
)

admin_router = APIRouter()
admin_router.include_router(locations.router)
admin_router.include_router(fleet.router)
admin_router.include_router(routes_admin.router)
admin_router.include_router(trips_admin.router)
admin_router.include_router(surcharges.router)
admin_router.include_router(website.router)
admin_router.include_router(bookings.router)
admin_router.include_router(hotels_admin.router)
admin_router.include_router(tours_admin.router)
admin_router.include_router(meta.router)
