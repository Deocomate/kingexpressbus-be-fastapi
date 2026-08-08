"""Hotel application package."""

from app.application.hotel.booking_creation import (
    available_inventory,
    compute_total,
    create_hotel_booking,
    rooms_booked,
)
from app.application.hotel.booking_status import update_hotel_booking_status
from app.application.hotel.shared import (
    ALL_STATUSES,
    COUNTED_STATUSES,
    PAYMENT_METHODS,
    BookingError,
    EmailAction,
    ServiceBookingResult,
    utcnow,
)

__all__ = [
    "ALL_STATUSES",
    "BookingError",
    "COUNTED_STATUSES",
    "EmailAction",
    "PAYMENT_METHODS",
    "ServiceBookingResult",
    "available_inventory",
    "compute_total",
    "create_hotel_booking",
    "rooms_booked",
    "update_hotel_booking_status",
    "utcnow",
]
