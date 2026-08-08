"""Admin schemas: trips, trip blocks."""

from datetime import date, time

from pydantic import BaseModel


class TripWrite(BaseModel):
    bus_id: int
    route_id: int
    start_time: time
    end_time: time
    price: int = 0
    is_active: bool = True
    priority: int | None = None


class TripOut(TripWrite):
    id: int
    priority: int
    route_name: str | None = None
    province_start_id: int | None = None
    province_start_name: str | None = None
    province_end_id: int | None = None
    province_end_name: str | None = None
    bus_name: str | None = None

    model_config = {"from_attributes": True}


class TripBlockWrite(BaseModel):
    trip_id: int
    start_date: date
    end_date: date
    block_type: str
    note: str | None = None


class TripBlockOut(TripBlockWrite):
    id: int

    model_config = {"from_attributes": True}
