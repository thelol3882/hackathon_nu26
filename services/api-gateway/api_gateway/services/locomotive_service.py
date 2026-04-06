"""Locomotive service — business logic, calls repository for DB access."""

from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from api_gateway.models.locomotive_entity import Locomotive
from api_gateway.repositories import locomotive_repository
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
    try:
        entity = await locomotive_repository.create(session, entity)
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Serial number already exists") from e
    return LocomotiveRead.model_validate(entity, from_attributes=True)


async def get_locomotive(session: AsyncSession, locomotive_id: str) -> LocomotiveRead:
    entity = await locomotive_repository.find_by_id(session, locomotive_id)
    if entity is None:
        raise HTTPException(status_code=404, detail="Locomotive not found")
    return LocomotiveRead.model_validate(entity, from_attributes=True)


async def list_locomotives(
    session: AsyncSession,
    *,
    offset: int = 0,
    limit: int = 50,
    search: str | None = None,
    model: str | None = None,
) -> LocomotiveListResponse:
    total = await locomotive_repository.count(session, search=search, model=model)
    items_entities = await locomotive_repository.find_many(
        session, offset=offset, limit=limit, search=search, model=model
    )
    items = [LocomotiveRead.model_validate(row, from_attributes=True) for row in items_entities]
    return LocomotiveListResponse(items=items, total=total)


async def get_fleet_ids(session: AsyncSession) -> list[dict]:
    return await locomotive_repository.get_fleet_ids(session)
