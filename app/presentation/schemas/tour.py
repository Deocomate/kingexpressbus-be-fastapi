"""Schemas for tours and tour bookings."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field


class TourOut(BaseModel):
    id: int
    name: str
    slug: str
    short_description: str | None = None
    description: str | None = None
    itinerary: str | None = None
    duration_label: str | None = None
    duration_hours: int | None = None
    base_price: int
    max_guests: int
    highlights: Any = None
    includes: Any = None
    excludes: Any = None
    thumbnail_url: str | None = None
    image_list_url: Any = None
    is_active: bool
    priority: int

    model_config = {"from_attributes": True}


class TourListOut(BaseModel):
    id: int
    name: str
    slug: str
    short_description: str | None = None
    duration_label: str | None = None
    base_price: int
    max_guests: int
    thumbnail_url: str | None = None
    is_active: bool
    priority: int

    model_config = {"from_attributes": True}


class TourWrite(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = None
    short_description: str | None = None
    description: str | None = None
    itinerary: str | None = None
    duration_label: str | None = None
    duration_hours: int | None = None
    base_price: int = Field(ge=0)
    max_guests: int = Field(ge=1, default=20)
    highlights: Any = None
    includes: Any = None
    excludes: Any = None
    thumbnail_url: str | None = None
    image_list_url: Any = None
    is_active: bool = True
    priority: int | None = None


class TourBookingCreateIn(BaseModel):
    tour_id: int
    tour_date: date
    guests: int = Field(ge=1, default=1)
    customer_name: str = Field(min_length=1, max_length=255)
    customer_email: EmailStr
    customer_phone: str | None = None
    payment_method: Literal["cash_at_property", "bank_transfer"] = "cash_at_property"
    total_price: int = Field(ge=0)
    notes: str | None = None


class TourBookingOut(BaseModel):
    id: int
    booking_code: str
    user_id: int | None = None
    tour_id: int
    tour_date: date
    guests: int
    unit_price: int
    total_price: int
    customer_name: str
    customer_email: str | None = None
    customer_phone: str | None = None
    status: str
    confirmed_at: datetime | None = None
    payment_method: str
    payment_status: str
    notes: str | None = None
    tour_name_snapshot: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class TourBookingCreateOut(BaseModel):
    booking: TourBookingOut
    success_url: str | None = None


class TourBookingCancelIn(BaseModel):
    reason: str | None = None


class TourBookingActionOut(BaseModel):
    success: bool
    message: str
    booking: TourBookingOut
