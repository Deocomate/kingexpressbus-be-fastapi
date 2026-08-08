"""Schemas for hotels, rooms, and hotel bookings."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, EmailStr, Field


class HotelRoomOut(BaseModel):
    id: int
    hotel_id: int
    name: str
    slug: str
    capacity_adults: int
    bed_label: str | None = None
    size_m2: int | None = None
    amenities: Any = None
    thumbnail_url: str | None = None
    image_list_url: Any = None
    base_price: int
    sale_price: int
    breakfast_price: int
    cancel_fee_percent: int
    inventory_count: int
    is_active: bool
    priority: int
    available_count: int | None = None

    model_config = {"from_attributes": True}


class HotelOut(BaseModel):
    id: int
    name: str
    slug: str
    address: str | None = None
    short_description: str | None = None
    description: str | None = None
    amenities: Any = None
    policies: Any = None
    thumbnail_url: str | None = None
    image_list_url: Any = None
    map_embedded: str | None = None
    check_in_from: str | None = None
    check_in_to: str | None = None
    check_out_from: str | None = None
    check_out_to: str | None = None
    rating_score: str | None = None
    rating_label: str | None = None
    rating_count: int = 0
    is_active: bool
    priority: int
    rooms: list[HotelRoomOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class HotelListOut(BaseModel):
    id: int
    name: str
    slug: str
    address: str | None = None
    short_description: str | None = None
    thumbnail_url: str | None = None
    rating_score: str | None = None
    rating_label: str | None = None
    rating_count: int = 0
    is_active: bool
    priority: int

    model_config = {"from_attributes": True}


class HotelWrite(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = None
    address: str | None = None
    short_description: str | None = None
    description: str | None = None
    amenities: Any = None
    policies: Any = None
    thumbnail_url: str | None = None
    image_list_url: Any = None
    map_embedded: str | None = None
    check_in_from: str | None = None
    check_in_to: str | None = None
    check_out_from: str | None = None
    check_out_to: str | None = None
    rating_score: str | None = None
    rating_label: str | None = None
    rating_count: int = 0
    is_active: bool = True
    priority: int | None = None


class HotelRoomWrite(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    slug: str | None = None
    capacity_adults: int = Field(ge=1, default=1)
    bed_label: str | None = None
    size_m2: int | None = None
    amenities: Any = None
    thumbnail_url: str | None = None
    image_list_url: Any = None
    base_price: int = Field(ge=0)
    sale_price: int = Field(ge=0)
    breakfast_price: int = Field(ge=0, default=0)
    cancel_fee_percent: int = Field(ge=0, le=100, default=0)
    inventory_count: int = Field(ge=1, default=1)
    is_active: bool = True
    priority: int | None = None


class HotelBookingCreateIn(BaseModel):
    room_id: int
    check_in: date
    check_out: date
    rooms_count: int = Field(ge=1, default=1)
    adults: int = Field(ge=1, default=1)
    children: int = Field(ge=0, default=0)
    breakfast_count: int = Field(ge=0, default=0)
    customer_name: str = Field(min_length=1, max_length=255)
    customer_email: EmailStr
    customer_phone: str | None = None
    payment_method: Literal["cash_at_property", "bank_transfer"] = "cash_at_property"
    total_price: int = Field(ge=0)
    notes: str | None = None


class HotelBookingOut(BaseModel):
    id: int
    booking_code: str
    user_id: int | None = None
    hotel_id: int
    room_id: int
    check_in: date
    check_out: date
    nights: int
    rooms_count: int
    adults: int
    children: int
    breakfast_count: int
    unit_price: int
    breakfast_unit_price: int
    total_price: int
    customer_name: str
    customer_email: str | None = None
    customer_phone: str | None = None
    status: str
    confirmed_at: datetime | None = None
    payment_method: str
    payment_status: str
    notes: str | None = None
    hotel_name_snapshot: str | None = None
    room_name_snapshot: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class HotelBookingCreateOut(BaseModel):
    booking: HotelBookingOut
    success_url: str | None = None


class HotelBookingCancelIn(BaseModel):
    reason: str | None = None


class HotelBookingActionOut(BaseModel):
    success: bool
    message: str
    booking: HotelBookingOut
