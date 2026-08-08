"""User and password-reset token models."""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.persistence.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)
    phone: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    email_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    # Nullable: guest checkout users have no login password.
    password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(String(32), default="customer")
    remember_token: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    email: Mapped[str] = mapped_column(String(255), primary_key=True)
    token: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class EmailVerificationToken(Base):
    __tablename__ = "email_verification_tokens"

    email: Mapped[str] = mapped_column(String(255), primary_key=True)
    token: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
