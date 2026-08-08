"""Admin CRUD: holiday surcharges (+ per-route additive amounts)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.application.catalog.admin_list import paginate
from app.core.deps import DbSession
from app.infrastructure.persistence.models import (
    HolidaySurcharge,
    HolidaySurchargeRoute,
)
from app.presentation.api.v1.admin.deps import AdminUser, SameOrigin
from app.presentation.schemas.admin_common import MessageOut, Paginated
from app.presentation.schemas.admin_surcharges import (
    SurchargeOut,
    SurchargeRouteAmount,
    SurchargeWrite,
)

router = APIRouter(prefix="/admin", tags=["admin-surcharges"])


def _out(row: HolidaySurcharge) -> SurchargeOut:
    return SurchargeOut(
        id=row.id,
        name=row.name,
        reason=row.reason,
        start_date=row.start_date,
        end_date=row.end_date,
        global_surcharge_amount=row.global_surcharge_amount,
        is_active=row.is_active,
        priority=row.priority,
        route_amounts=[
            SurchargeRouteAmount(
                route_id=p.route_id,
                route_surcharge_amount=p.route_surcharge_amount,
            )
            for p in (row.route_amounts or [])
        ],
    )


async def _replace_pivots(
    db: DbSession, surcharge_id: int, amounts: list[SurchargeRouteAmount]
) -> None:
    await db.execute(
        delete(HolidaySurchargeRoute).where(
            HolidaySurchargeRoute.holiday_surcharge_id == surcharge_id
        )
    )
    for a in amounts:
        db.add(
            HolidaySurchargeRoute(
                holiday_surcharge_id=surcharge_id,
                route_id=a.route_id,
                route_surcharge_amount=a.route_surcharge_amount,
            )
        )


@router.get("/surcharges", response_model=Paginated[SurchargeOut])
async def list_surcharges(
    db: DbSession, _: AdminUser, page: int = 1, page_size: int = 25
) -> Paginated[SurchargeOut]:
    stmt = (
        select(HolidaySurcharge)
        .options(selectinload(HolidaySurcharge.route_amounts))
        .order_by(HolidaySurcharge.priority.desc(), HolidaySurcharge.start_date.desc())
    )
    items, total = await paginate(db, stmt, page=page, page_size=page_size)
    return Paginated(
        items=[_out(i) for i in items],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("/surcharges", response_model=SurchargeOut, status_code=201)
async def create_surcharge(
    body: SurchargeWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> SurchargeOut:
    if body.end_date < body.start_date:
        raise HTTPException(422, detail="end_date must be >= start_date")
    row = HolidaySurcharge(
        name=body.name,
        reason=body.reason,
        start_date=body.start_date,
        end_date=body.end_date,
        global_surcharge_amount=body.global_surcharge_amount,
        is_active=body.is_active,
        priority=body.priority,
    )
    db.add(row)
    await db.flush()
    await _replace_pivots(db, row.id, body.route_amounts)
    await db.commit()
    result = await db.execute(
        select(HolidaySurcharge)
        .options(selectinload(HolidaySurcharge.route_amounts))
        .where(HolidaySurcharge.id == row.id)
    )
    return _out(result.scalar_one())


@router.get("/surcharges/{item_id}", response_model=SurchargeOut)
async def get_surcharge(item_id: int, db: DbSession, _: AdminUser) -> SurchargeOut:
    result = await db.execute(
        select(HolidaySurcharge)
        .options(selectinload(HolidaySurcharge.route_amounts))
        .where(HolidaySurcharge.id == item_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(404, detail="Not found")
    return _out(row)


@router.put("/surcharges/{item_id}", response_model=SurchargeOut)
async def update_surcharge(
    item_id: int, body: SurchargeWrite, db: DbSession, _: AdminUser, __: SameOrigin
) -> SurchargeOut:
    row = await db.get(HolidaySurcharge, item_id)
    if not row:
        raise HTTPException(404, detail="Not found")
    row.name = body.name
    row.reason = body.reason
    row.start_date = body.start_date
    row.end_date = body.end_date
    row.global_surcharge_amount = body.global_surcharge_amount
    row.is_active = body.is_active
    row.priority = body.priority
    await _replace_pivots(db, row.id, body.route_amounts)
    await db.commit()
    result = await db.execute(
        select(HolidaySurcharge)
        .options(selectinload(HolidaySurcharge.route_amounts))
        .where(HolidaySurcharge.id == item_id)
    )
    return _out(result.scalar_one())


@router.delete("/surcharges/{item_id}", response_model=MessageOut)
async def delete_surcharge(
    item_id: int, db: DbSession, _: AdminUser, __: SameOrigin
) -> MessageOut:
    row = await db.get(HolidaySurcharge, item_id)
    if not row:
        raise HTTPException(404, detail="Not found")
    await db.delete(row)
    await db.commit()
    return MessageOut(message="Deleted")
