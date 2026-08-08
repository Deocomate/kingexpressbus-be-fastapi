"""Tour catalog and tour booking models."""

from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.mysql import JSON, LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.base import Base, TimestampMixin


class Tour(Base, TimestampMixin):
    __tablename__ = "tours"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    short_description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(LONGTEXT, nullable=True)
    itinerary: Mapped[Optional[str]] = mapped_column(LONGTEXT, nullable=True)
    duration_label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    duration_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    base_price: Mapped[int] = mapped_column(BigInteger, default=0)
    max_guests: Mapped[int] = mapped_column(Integer, default=20)
    highlights: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    includes: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    excludes: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    image_list_url: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)


class TourBooking(Base, TimestampMixin):
    __tablename__ = "tour_bookings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    booking_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    tour_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("tours.id", ondelete="CASCADE"), index=True
    )
    tour_date: Mapped[date] = mapped_column(Date)
    guests: Mapped[int] = mapped_column(Integer, default=1)
    unit_price: Mapped[int] = mapped_column(BigInteger, default=0)
    total_price: Mapped[int] = mapped_column(BigInteger, default=0)
    customer_name: Mapped[str] = mapped_column(String(255))
    customer_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    customer_phone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    payment_method: Mapped[str] = mapped_column(String(64), default="cash_at_property")
    payment_status: Mapped[str] = mapped_column(String(32), default="unpaid")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tour_name_snapshot: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
