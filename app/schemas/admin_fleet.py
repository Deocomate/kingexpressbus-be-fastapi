"""Admin schemas: bus services, buses."""

from typing import Any

from pydantic import BaseModel, Field


class BusServiceWrite(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    icon: str | None = None
    priority: int | None = None


class BusServiceOut(BusServiceWrite):
    id: int
    priority: int

    model_config = {"from_attributes": True}


class BusWrite(BaseModel):
    name: str = Field(min_length=1, max_length=1000)
    model_name: str | None = None
    seat_count: int = Field(ge=1)
    thumbnail_url: str | None = None
    image_list_url: Any = None
    content: str | None = None
    service_ids: list[int] = Field(default_factory=list)
    priority: int | None = None


class BusOut(BaseModel):
    id: int
    name: str
    model_name: str | None = None
    seat_count: int
    thumbnail_url: str | None = None
    image_list_url: Any = None
    content: str | None = None
    priority: int
    service_ids: list[int] = Field(default_factory=list)

    model_config = {"from_attributes": True}
