"""Booking model — mirrors Laravel bookings DDL exactly."""

from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class Booking(Base, TimestampMixin):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    booking_code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    trip_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("trips.id", ondelete="CASCADE")
    )
    booking_date: Mapped[date] = mapped_column(Date)
    customer_name: Mapped[str] = mapped_column(String(255))
    customer_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    customer_phone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    pickup_stop_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("stops.id", ondelete="SET NULL"), nullable=True
    )
    dropoff_stop_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stops.id", ondelete="CASCADE")
    )
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    base_unit_price: Mapped[int] = mapped_column(BigInteger, default=0)
    global_surcharge_unit: Mapped[int] = mapped_column(BigInteger, default=0)
    route_surcharge_unit: Mapped[int] = mapped_column(BigInteger, default=0)
    final_unit_price: Mapped[int] = mapped_column(BigInteger, default=0)
    total_surcharge_amount: Mapped[int] = mapped_column(BigInteger, default=0)
    total_price: Mapped[int] = mapped_column(BigInteger, default=0)
    surcharge_reason_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    payment_method: Mapped[str] = mapped_column(String(64), default="cash_on_pickup")
    payment_status: Mapped[str] = mapped_column(String(32), default="unpaid")
    payment_transaction_id: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    payment_log: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
