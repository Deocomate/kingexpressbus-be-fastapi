"""Routes, trips, route stops, and trip blocks."""

from datetime import date, time
from typing import Any, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    ForeignKey,
    Integer,
    String,
    Text,
    Time,
)
from sqlalchemy.dialects.mysql import JSON, LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.persistence.base import Base, TimestampMixin


class Route(Base, TimestampMixin):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    province_start_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("provinces.id", ondelete="CASCADE")
    )
    province_end_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("provinces.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(1000))
    slug: Mapped[str] = mapped_column(String(255), unique=True)
    title: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    duration: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    distance_km: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    price_default: Mapped[int] = mapped_column(BigInteger, default=0)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    image_list_url: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    content: Mapped[Optional[str]] = mapped_column(LONGTEXT, nullable=True)
    available_hotel_pickup: Mapped[bool] = mapped_column(Boolean, default=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)

    route_stops: Mapped[list["RouteStop"]] = relationship(
        back_populates="route", passive_deletes=True
    )
    trips: Mapped[list["Trip"]] = relationship(back_populates="route", passive_deletes=True)


class RouteStop(Base, TimestampMixin):
    __tablename__ = "route_stops"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    route_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("routes.id", ondelete="CASCADE")
    )
    stop_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("stops.id", ondelete="CASCADE")
    )
    stop_type: Mapped[str] = mapped_column(String(32), default="both")
    priority: Mapped[int] = mapped_column(Integer, default=0)

    route: Mapped[Route] = relationship(back_populates="route_stops")


class Trip(Base, TimestampMixin):
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    bus_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("buses.id", ondelete="CASCADE")
    )
    route_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("routes.id", ondelete="CASCADE")
    )
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    price: Mapped[int] = mapped_column(BigInteger, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)

    route: Mapped[Route] = relationship(back_populates="trips")
    blocks: Mapped[list["TripBlock"]] = relationship(
        back_populates="trip", passive_deletes=True
    )


class TripBlock(Base, TimestampMixin):
    __tablename__ = "trip_blocks"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    trip_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("trips.id", ondelete="CASCADE")
    )
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    block_type: Mapped[str] = mapped_column(String(255))
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    trip: Mapped[Trip] = relationship(back_populates="blocks")
