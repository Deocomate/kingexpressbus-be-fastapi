"""Admin schemas: web profile, menus."""

from pydantic import BaseModel, Field


class WebProfileWrite(BaseModel):
    profile_name: str | None = None
    is_default: bool | None = None
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


class WebProfileAdminOut(WebProfileWrite):
    id: int
    profile_name: str
    is_default: bool

    model_config = {"from_attributes": True}


class MenuWrite(BaseModel):
    name: str = Field(min_length=1, max_length=1000)
    url: str | None = None
    parent_id: int | None = -1
    priority: int | None = None
    type: str = "custom_link"
    related_id: int | None = None


class MenuOut(BaseModel):
    id: int
    name: str
    url: str | None = None
    parent_id: int | None = None
    priority: int
    type: str
    related_id: int | None = None

    model_config = {"from_attributes": True}


class MenuTreeReorderItem(BaseModel):
    id: int
    parent_id: int | None = -1
    priority: int


class MenuTreeReorderRequest(BaseModel):
    items: list[MenuTreeReorderItem]
