"""Shared admin list / reorder / message schemas."""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Paginated(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class ReorderRequest(BaseModel):
    ids: list[int] = Field(min_length=1)


class MessageOut(BaseModel):
    message: str


class OptionItem(BaseModel):
    id: int
    text: str


class OptionsOut(BaseModel):
    results: list[OptionItem]


class IdListRequest(BaseModel):
    ids: list[int] = Field(min_length=1)


class ErrorDetail(BaseModel):
    detail: str
    booking_count: int | None = None
