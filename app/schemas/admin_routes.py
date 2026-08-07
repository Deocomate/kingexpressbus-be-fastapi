"""Admin schemas: routes, route stops."""

from typing import Any

from pydantic import BaseModel, Field


class RouteWrite(BaseModel):
    province_start_id: int
    province_end_id: int
    name: str = Field(min_length=1, max_length=1000)
    slug: str | None = None
    title: str | None = None
    description: str | None = None
    duration: str | None = None
    distance_km: int | None = None
    price_default: int = 0
    thumbnail_url: str | None = None
    image_list_url: Any = None
    content: str | None = None
    available_hotel_pickup: bool = False
    priority: int | None = None


class RouteOut(RouteWrite):
    id: int
    slug: str
    priority: int
    province_start_name: str | None = None
    province_end_name: str | None = None

    model_config = {"from_attributes": True}


class RouteStopWrite(BaseModel):
    stop_id: int
    stop_type: str = "both"
    priority: int | None = None


class RouteStopOut(BaseModel):
    id: int
    route_id: int
    stop_id: int
    stop_type: str
    priority: int
    stop_name: str | None = None
    stop_address: str | None = None

    model_config = {"from_attributes": True}
