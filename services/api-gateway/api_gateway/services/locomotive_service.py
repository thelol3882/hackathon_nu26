"""CRUD operations for the locomotive registry."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api_gateway.models.locomotive_entity import Locomotive
from shared.schemas.locomotive import LocomotiveCreate, LocomotiveRead
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


async def list_locomotives(session: AsyncSession, offset: int = 0, limit: int = 50) -> list[LocomotiveRead]:
    result = await session.execute(
        select(Locomotive).order_by(Locomotive.created_at.desc()).offset(offset).limit(limit)
    )
    return [LocomotiveRead.model_validate(row, from_attributes=True) for row in result.scalars().all()]
