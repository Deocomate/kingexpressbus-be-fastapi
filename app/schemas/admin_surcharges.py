"""Admin schemas: holiday surcharges."""

from datetime import date

from pydantic import BaseModel, Field


class SurchargeRouteAmount(BaseModel):
    route_id: int
    route_surcharge_amount: int = 0


class SurchargeWrite(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    reason: str | None = None
    start_date: date
    end_date: date
    global_surcharge_amount: int = 0
    is_active: bool = True
    priority: int = 0
    route_amounts: list[SurchargeRouteAmount] = Field(default_factory=list)


class SurchargeOut(BaseModel):
    id: int
    name: str
    reason: str | None = None
    start_date: date
    end_date: date
    global_surcharge_amount: int
    is_active: bool
    priority: int
    route_amounts: list[SurchargeRouteAmount] = Field(default_factory=list)

    model_config = {"from_attributes": True}
