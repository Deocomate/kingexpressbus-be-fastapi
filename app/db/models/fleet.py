"""Fleet models: buses and bus services."""

from typing import Any, Optional

from sqlalchemy import BigInteger, Column, ForeignKey, Integer, String, Table
from sqlalchemy.dialects.mysql import JSON, LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

bus_bus_service = Table(
    "bus_bus_service",
    Base.metadata,
    Column(
        "bus_id",
        BigInteger,
        ForeignKey("buses.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "bus_service_id",
        BigInteger,
        ForeignKey("bus_services.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class BusService(Base):
    __tablename__ = "bus_services"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    icon: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)


class Bus(Base, TimestampMixin):
    __tablename__ = "buses"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(1000))
    model_name: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    seat_count: Mapped[int] = mapped_column(Integer)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    image_list_url: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    content: Mapped[Optional[str]] = mapped_column(LONGTEXT, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)

    services: Mapped[list[BusService]] = relationship(
        secondary=bus_bus_service, lazy="selectin"
    )
