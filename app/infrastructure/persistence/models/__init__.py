"""Import all models so Alembic / metadata see every table."""

from app.infrastructure.persistence.models.booking import Booking
from app.infrastructure.persistence.models.fleet import Bus, BusService, bus_bus_service
from app.infrastructure.persistence.models.hotel import Hotel, HotelBooking, HotelRoom
from app.infrastructure.persistence.models.location import (
    District,
    DistrictType,
    Province,
    Stop,
)
from app.infrastructure.persistence.models.mail_queue import FailedMailJob, MailJob
from app.infrastructure.persistence.models.ops import Route, RouteStop, Trip, TripBlock
from app.infrastructure.persistence.models.surcharge import (
    HolidaySurcharge,
    HolidaySurchargeRoute,
)
from app.infrastructure.persistence.models.tour import Tour, TourBooking
from app.infrastructure.persistence.models.user import (
    EmailVerificationToken,
    PasswordResetToken,
    User,
)
from app.infrastructure.persistence.models.website import Menu, WebProfile

__all__ = [
    "Booking",
    "Bus",
    "BusService",
    "bus_bus_service",
    "District",
    "DistrictType",
    "EmailVerificationToken",
    "FailedMailJob",
    "HolidaySurcharge",
    "HolidaySurchargeRoute",
    "Hotel",
    "HotelBooking",
    "HotelRoom",
    "MailJob",
    "Menu",
    "PasswordResetToken",
    "Province",
    "Route",
    "RouteStop",
    "Stop",
    "Tour",
    "TourBooking",
    "Trip",
    "TripBlock",
    "User",
    "WebProfile",
]
