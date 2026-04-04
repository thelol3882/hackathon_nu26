"""CRUD operations for the locomotive registry."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api_gateway.models.locomotive_entity import Locomotive
from shared.schemas.locomotive import LocomotiveCreate, LocomotiveListResponse, LocomotiveRead
from shared.utils import generate_id


async def create_locomotive(session: AsyncSession, data: LocomotiveCreate) -> LocomotiveRead:
    entity = Locomotive(
        id=generate_id(),
        serial_number=data.serial_number,
        model=data.model,
        manufacturer=data.manufacturer,
        year_manufactured=data.year_manufactured,
    )
    session.add(entity)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Serial number already exists") from e
    await session.refresh(entity)
    return LocomotiveRead.model_validate(entity, from_attributes=True)


async def get_locomotive(session: AsyncSession, locomotive_id: str) -> LocomotiveRead:
    result = await session.execute(select(Locomotive).where(Locomotive.id == locomotive_id))
    entity = result.scalar_one_or_none()
    if entity is None:
        raise HTTPException(status_code=404, detail="Locomotive not found")
    return LocomotiveRead.model_validate(entity, from_attributes=True)


def _apply_filters(
    stmt,
    *,
    search: str | None = None,
    model: str | None = None,
):
    if model:
        stmt = stmt.where(Locomotive.model.ilike(f"{model}%"))
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(
                Locomotive.serial_number.ilike(pattern),
                Locomotive.model.ilike(pattern),
            )
        )
    return stmt


async def list_locomotives(
    session: AsyncSession,
    *,
    offset: int = 0,
    limit: int = 50,
    search: str | None = None,
    model: str | None = None,
) -> LocomotiveListResponse:
    base = select(Locomotive)
    base = _apply_filters(base, search=search, model=model)

    count_result = await session.execute(select(func.count()).select_from(base.subquery()))
    total = count_result.scalar_one()

    rows_result = await session.execute(
        base.order_by(Locomotive.serial_number).offset(offset).limit(limit)
    )
    items = [LocomotiveRead.model_validate(row, from_attributes=True) for row in rows_result.scalars().all()]

    return LocomotiveListResponse(items=items, total=total)


async def get_fleet_ids(session: AsyncSession) -> list[dict]:
    """Return minimal id+model for every locomotive (used by simulator)."""
    result = await session.execute(
        select(Locomotive.id, Locomotive.model).order_by(Locomotive.serial_number)
    )
    return [{"id": str(row.id), "model": row.model} for row in result.all()]
