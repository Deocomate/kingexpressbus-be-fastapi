"""Location models: provinces, district types, districts, stops."""

from typing import Any, Optional

from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.dialects.mysql import JSON, LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.persistence.base import Base, TimestampMixin


class Province(Base, TimestampMixin):
    __tablename__ = "provinces"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), unique=True)
    title: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    image_list_url: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    content: Mapped[Optional[str]] = mapped_column(LONGTEXT, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)

    districts: Mapped[list["District"]] = relationship(
        back_populates="province", passive_deletes=True
    )


class DistrictType(Base, TimestampMixin):
    __tablename__ = "district_types"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    priority: Mapped[int] = mapped_column(Integer, default=0)


class District(Base, TimestampMixin):
    __tablename__ = "districts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    province_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("provinces.id", ondelete="CASCADE")
    )
    district_type_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("district_types.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(255), unique=True)
    title: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    thumbnail_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    image_list_url: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    content: Mapped[Optional[str]] = mapped_column(LONGTEXT, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)

    province: Mapped[Province] = relationship(back_populates="districts")
    stops: Mapped[list["Stop"]] = relationship(
        back_populates="district", passive_deletes=True
    )


class Stop(Base, TimestampMixin):
    __tablename__ = "stops"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    district_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("districts.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(255))
    address: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)

    district: Mapped[District] = relationship(back_populates="stops")
