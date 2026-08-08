"""Booking request/response schemas."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

PaymentMethod = Literal["cash_on_pickup", "online_banking"]
BookingStatus = Literal["pending", "confirmed", "completed", "cancelled"]


class BookingCreateIn(BaseModel):
    trip_id: int
    booking_date: date
    quantity: int = Field(ge=1)
    customer_name: str
    customer_phone: str
    customer_email: EmailStr
    dropoff_stop_id: int
    total_price: int
    payment_method: PaymentMethod
    pickup_stop_id: int | None = None
    is_hotel_pickup: bool = False
    hotel_pickup_address: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def require_pickup_or_hotel(self) -> BookingCreateIn:
        if self.is_hotel_pickup:
            if not (self.hotel_pickup_address and self.hotel_pickup_address.strip()):
                raise ValueError("hotel_pickup_address required when is_hotel_pickup")
        elif self.pickup_stop_id is None:
            raise ValueError("pickup_stop_id or is_hotel_pickup required")
        return self


class BookingOut(BaseModel):
    """Full booking — admin or signature-gated public success page."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    booking_code: str
    trip_id: int
    booking_date: date
    customer_name: str
    customer_email: str | None = None
    customer_phone: str | None = None
    pickup_stop_id: int | None = None
    dropoff_stop_id: int
    quantity: int
    base_unit_price: int
    global_surcharge_unit: int
    route_surcharge_unit: int
    final_unit_price: int
    total_surcharge_amount: int
    total_price: int
    surcharge_reason_snapshot: str | None = None
    status: str
    confirmed_at: datetime | None = None
    created_at: datetime | None = None
    payment_method: str
    payment_status: str
    payment_transaction_id: str | None = None
    notes: str | None = None
    success_url: str | None = None


class BookingReceiptOut(BaseModel):
    """Unauthenticated by-code lookup — no customer PII."""

    model_config = ConfigDict(from_attributes=True)

    booking_code: str
    trip_id: int
    booking_date: date
    quantity: int
    total_price: int
    status: str
    payment_method: str
    payment_status: str


class BookingCreateOut(BaseModel):
    success: bool = True
    booking_id: int
    booking_code: str
    success_url: str
    booking: BookingOut


class PriceChangedOut(BaseModel):
    error: Literal["price_changed"] = "price_changed"
    submitted_total: int
    breakdown: dict[str, Any]


class PaymentStatusOut(BaseModel):
    found: bool
    booking_code: str | None = None
    status: str | None = None
    payment_method: str | None = None
    payment_status: str | None = None


class SignedSuccessVerifyIn(BaseModel):
    booking_id: int
    expires: int
    signature: str


class SignedSuccessVerifyOut(BaseModel):
    valid: bool
    booking_id: int | None = None


class SepayCheckoutOut(BaseModel):
    booking_code: str
    html_form: str


class BookingAdminUpdateIn(BaseModel):
    """Admin edit — customer/stop/quantity/notes only.

    status/payment_status/confirmed_at/payment_transaction_id are
    intentionally absent: those move only through the confirm/cancel/
    complete/status action endpoints (mail + confirmed_at + refund-note side
    effects). Price is server-recomputed, never accepted here.
    """

    customer_name: str
    customer_phone: str
    customer_email: EmailStr | None = None
    dropoff_stop_id: int
    pickup_stop_id: int | None = None
    quantity: int = Field(ge=1)
    notes: str | None = None
    hotel_pickup_address: str | None = None


class BookingStatusUpdateIn(BaseModel):
    status: BookingStatus
    notes: str | None = None


class BookingCancelIn(BaseModel):
    reason: str | None = None


class BookingActionOut(BaseModel):
    success: bool
    message: str
    booking: BookingOut | None = None
