"""Hotel, room types, and hotel booking models."""

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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.persistence.base import Base, TimestampMixin


class Hotel(Base, TimestampMixin):
    __tablename__ = "hotels"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    address: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    short_description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(LONGTEXT, nullable=True)
    amenities: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    policies: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    image_list_url: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    map_embedded: Mapped[Optional[str]] = mapped_column(LONGTEXT, nullable=True)
    check_in_from: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    check_in_to: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    check_out_from: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    check_out_to: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    rating_score: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    rating_label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)

    rooms: Mapped[list["HotelRoom"]] = relationship(
        back_populates="hotel", lazy="selectin"
    )


class HotelRoom(Base, TimestampMixin):
    __tablename__ = "hotel_rooms"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    hotel_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hotels.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), index=True)
    capacity_adults: Mapped[int] = mapped_column(Integer, default=1)
    bed_label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    size_m2: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    amenities: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    image_list_url: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    base_price: Mapped[int] = mapped_column(BigInteger, default=0)
    sale_price: Mapped[int] = mapped_column(BigInteger, default=0)
    breakfast_price: Mapped[int] = mapped_column(BigInteger, default=0)
    cancel_fee_percent: Mapped[int] = mapped_column(Integer, default=0)
    inventory_count: Mapped[int] = mapped_column(Integer, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)

    hotel: Mapped[Hotel] = relationship(back_populates="rooms")


class HotelBooking(Base, TimestampMixin):
    __tablename__ = "hotel_bookings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    booking_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    hotel_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hotels.id", ondelete="CASCADE"), index=True
    )
    room_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("hotel_rooms.id", ondelete="CASCADE"), index=True
    )
    check_in: Mapped[date] = mapped_column(Date)
    check_out: Mapped[date] = mapped_column(Date)
    nights: Mapped[int] = mapped_column(Integer, default=1)
    rooms_count: Mapped[int] = mapped_column(Integer, default=1)
    adults: Mapped[int] = mapped_column(Integer, default=1)
    children: Mapped[int] = mapped_column(Integer, default=0)
    breakfast_count: Mapped[int] = mapped_column(Integer, default=0)
    unit_price: Mapped[int] = mapped_column(BigInteger, default=0)
    breakfast_unit_price: Mapped[int] = mapped_column(BigInteger, default=0)
    total_price: Mapped[int] = mapped_column(BigInteger, default=0)
    customer_name: Mapped[str] = mapped_column(String(255))
    customer_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    customer_phone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    payment_method: Mapped[str] = mapped_column(String(64), default="cash_at_property")
    payment_status: Mapped[str] = mapped_column(String(32), default="unpaid")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hotel_name_snapshot: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    room_name_snapshot: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
