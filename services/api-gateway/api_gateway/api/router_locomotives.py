from datetime import datetime

from fastapi import APIRouter, Query

from api_gateway.api.dependencies import DbSession, Redis
from api_gateway.services import locomotive_service
from api_gateway.services.health_service import get_health_at, get_health_index
from shared.schemas.health import HealthIndex
from shared.schemas.locomotive import LocomotiveCreate, LocomotiveListResponse, LocomotiveRead

router = APIRouter()


@router.get("/", response_model=LocomotiveListResponse)
async def list_locomotives(
    db: DbSession,
    offset: int = 0,
    limit: int = 50,
    search: str | None = Query(None, description="Search by serial number or model"),
    model: str | None = Query(None, description="Filter by model (e.g. TE33A, KZ8A)"),
):
    """List registered locomotives with optional search and filtering."""
    return await locomotive_service.list_locomotives(
        db,
        offset=offset,
        limit=limit,
        search=search,
        model=model,
    )


@router.get("/fleet", response_model=list[dict])
async def get_fleet_ids(db: DbSession):
    """Lightweight endpoint for simulator: returns all locomotive IDs and models."""
    return await locomotive_service.get_fleet_ids(db)


@router.post("/", status_code=201, response_model=LocomotiveRead)
async def create_locomotive(data: LocomotiveCreate, db: DbSession):
    """Register a new locomotive."""
    return await locomotive_service.create_locomotive(db, data)


@router.get("/{locomotive_id}", response_model=LocomotiveRead)
async def get_locomotive(locomotive_id: str, db: DbSession):
    """Get a single locomotive by ID."""
    return await locomotive_service.get_locomotive(db, locomotive_id)


@router.get("/{locomotive_id}/health", response_model=HealthIndex)
async def get_locomotive_health(locomotive_id: str, db: DbSession, redis: Redis):
    """Get the current health index for a locomotive."""
    return await get_health_index(db, redis, locomotive_id)


@router.get("/{locomotive_id}/health/at", response_model=HealthIndex)
async def get_locomotive_health_at(
    locomotive_id: str,
    db: DbSession,
    at: datetime = Query(..., description="Point in time (ISO 8601)"),
):
    """Get the health index at a specific point in time (replay)."""
    return await get_health_at(db, locomotive_id, at)
