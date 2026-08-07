"""Website profile and menu models."""

from typing import Optional

from sqlalchemy import BigInteger, Boolean, Integer, String
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin


class WebProfile(Base, TimestampMixin):
    __tablename__ = "web_profiles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    profile_name: Mapped[str] = mapped_column(String(255))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    title: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    favicon_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    hotline: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    whatsapp: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    facebook_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    zalo_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    map_embedded: Mapped[Optional[str]] = mapped_column(LONGTEXT, nullable=True)
    policy_content: Mapped[Optional[str]] = mapped_column(LONGTEXT, nullable=True)
    introduction_content: Mapped[Optional[str]] = mapped_column(LONGTEXT, nullable=True)


class Menu(Base, TimestampMixin):
    __tablename__ = "menus"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    parent_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    type: Mapped[str] = mapped_column(String(64), default="custom_link")
    related_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
