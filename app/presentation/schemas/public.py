"""Public read API schemas."""

from datetime import date, time
from typing import Any

from pydantic import BaseModel, Field


class WebProfileOut(BaseModel):
    id: int
    profile_name: str
    online_payment_enabled: bool = True
    title: str | None = None
    description: str | None = None
    logo_url: str | None = None
    favicon_url: str | None = None
    email: str | None = None
    phone: str | None = None
    hotline: str | None = None
    whatsapp: str | None = None
    address: str | None = None
    facebook_url: str | None = None
    zalo_url: str | None = None
    map_embedded: str | None = None
    policy_content: str | None = None
    introduction_content: str | None = None

    model_config = {"from_attributes": True}


class MenuNodeOut(BaseModel):
    id: int
    name: str
    url: str | None = None
    parent_id: int | None = None
    priority: int
    type: str
    related_id: int | None = None
    children: list["MenuNodeOut"] = Field(default_factory=list)


class ProvinceOut(BaseModel):
    id: int
    name: str
    slug: str
    title: str | None = None
    description: str | None = None
    thumbnail_url: str | None = None
    priority: int

    model_config = {"from_attributes": True}


class RouteListOut(BaseModel):
    id: int
    name: str
    slug: str
    province_start_id: int
    province_end_id: int
    duration: str | None = None
    distance_km: int | None = None
    price_default: int
    thumbnail_url: str | None = None
    available_hotel_pickup: bool
    priority: int

    model_config = {"from_attributes": True}


class PriceBreakdownOut(BaseModel):
    travel_date: str
    base_unit_price: int
    global_surcharge_unit: int
    route_surcharge_unit: int
    total_surcharge_unit: int
    final_unit_price: int
    has_surcharge: bool
    surcharge_reasons: list[str]
    surcharge_reason_snapshot: str | None = None


class TripSearchItemOut(BaseModel):
    trip_id: int
    route_id: int
    bus_id: int
    start_time: time
    end_time: time
    price: int
    priority: int
    route_name: str
    route_slug: str
    duration: str | None = None
    distance_km: int | None = None
    available_hotel_pickup: bool
    bus_name: str
    bus_model: str | None = None
    seat_count: int
    available_seats: int
    is_blocked: bool = False
    block_type: str | None = None
    bus_services: list[str] = Field(default_factory=list)
    effective_price: int | None = None
    has_surcharge: bool = False
    bus_images: Any = None
    thumbnail_url: str | None = None


class TripDetailOut(TripSearchItemOut):
    start_province_name: str | None = None
    end_province_name: str | None = None
    bus_content: str | None = None
    is_off_day: bool = False
    block_note: str | None = None
    price_breakdown: PriceBreakdownOut | None = None
    stops: list[dict[str, Any]] = Field(default_factory=list)


class TripSearchQuery(BaseModel):
    origin_province_id: int
    destination_province_id: int
    date: date


class OfficeOut(BaseModel):
    id: int
    name: str
    address: str | None = None
    district_name: str


class OfficeProvinceGroupOut(BaseModel):
    province_id: int
    province_name: str
    offices: list[OfficeOut] = Field(default_factory=list)
