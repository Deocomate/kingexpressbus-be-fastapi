"""Admin location schemas: provinces, district types, districts, stops."""


from typing import Any

from pydantic import BaseModel, Field


# ── Provinces ──────────────────────────────────────────────────────────────
class ProvinceWrite(BaseModel):
    name: str = Field(min_length=1, max_length=1000)
    slug: str | None = None
    title: str | None = None
    description: str | None = None
    thumbnail_url: str | None = None
    image_list_url: Any = None
    content: str | None = None
    priority: int | None = None


class ProvinceOut(ProvinceWrite):
    id: int
    slug: str
    priority: int

    model_config = {"from_attributes": True}


# ── District types ─────────────────────────────────────────────────────────
class DistrictTypeWrite(BaseModel):
    name: str = Field(min_length=1, max_length=1000)
    priority: int | None = None


class DistrictTypeOut(DistrictTypeWrite):
    id: int
    priority: int

    model_config = {"from_attributes": True}


# ── Districts ──────────────────────────────────────────────────────────────
class DistrictWrite(BaseModel):
    province_id: int
    district_type_id: int
    name: str = Field(min_length=1, max_length=1000)
    slug: str | None = None
    title: str | None = None
    description: str | None = None
    thumbnail_url: str | None = None
    image_list_url: Any = None
    content: str | None = None
    priority: int | None = None


class DistrictOut(DistrictWrite):
    id: int
    slug: str
    priority: int

    model_config = {"from_attributes": True}


# ── Stops ──────────────────────────────────────────────────────────────────
class StopWrite(BaseModel):
    district_id: int
    name: str = Field(min_length=1, max_length=1000)
    address: str = Field(min_length=1, max_length=1000)
    priority: int | None = None


class StopOut(StopWrite):
    id: int
    priority: int
    province_id: int | None = None
    province_name: str | None = None
    district_name: str | None = None

    model_config = {"from_attributes": True}
