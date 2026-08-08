"""Holiday surcharge models."""

from datetime import date
from typing import Optional

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.persistence.base import Base, TimestampMixin


class HolidaySurcharge(Base, TimestampMixin):
    __tablename__ = "holiday_surcharges"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    global_surcharge_amount: Mapped[int] = mapped_column(BigInteger, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)

    route_amounts: Mapped[list["HolidaySurchargeRoute"]] = relationship(
        back_populates="surcharge", cascade="all, delete-orphan"
    )


class HolidaySurchargeRoute(Base, TimestampMixin):
    __tablename__ = "holiday_surcharge_routes"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    holiday_surcharge_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("holiday_surcharges.id", ondelete="CASCADE")
    )
    route_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("routes.id", ondelete="CASCADE")
    )
    route_surcharge_amount: Mapped[int] = mapped_column(BigInteger, default=0)

    surcharge: Mapped[HolidaySurcharge] = relationship(back_populates="route_amounts")
