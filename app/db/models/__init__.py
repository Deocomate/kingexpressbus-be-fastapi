"""Import all models so Alembic / metadata see every table."""

from app.db.models.booking import Booking
from app.db.models.fleet import Bus, BusService, bus_bus_service
from app.db.models.location import District, DistrictType, Province, Stop
from app.db.models.mail_queue import FailedMailJob, MailJob
from app.db.models.ops import Route, RouteStop, Trip, TripBlock
from app.db.models.surcharge import HolidaySurcharge, HolidaySurchargeRoute
from app.db.models.user import PasswordResetToken, User, EmailVerificationToken
from app.db.models.website import Menu, WebProfile

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
    "MailJob",
    "Menu",
    "PasswordResetToken",
    "Province",
    "Route",
    "RouteStop",
    "Stop",
    "Trip",
    "TripBlock",
    "User",
    "WebProfile",
]
