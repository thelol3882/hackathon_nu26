from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from api_gateway.api.dependencies import Analytics, AppSession
from api_gateway.services import locomotive_service
from shared.schemas.health import HealthFactor, HealthIndex
from shared.schemas.locomotive import LocomotiveCreate, LocomotiveListResponse, LocomotiveRead

router = APIRouter()


@router.get("/", response_model=LocomotiveListResponse)
async def list_locomotives(
    db: AppSession,
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
async def get_fleet_ids(db: AppSession):
    """Lightweight endpoint for simulator: returns all locomotive IDs and models."""
    return await locomotive_service.get_fleet_ids(db)


@router.post("/", status_code=201, response_model=LocomotiveRead)
async def create_locomotive(data: LocomotiveCreate, db: AppSession):
    """Register a new locomotive."""
    return await locomotive_service.create_locomotive(db, data)


@router.get("/{locomotive_id}", response_model=LocomotiveRead)
async def get_locomotive(locomotive_id: str, db: AppSession):
    """Get a single locomotive by ID."""
    return await locomotive_service.get_locomotive(db, locomotive_id)


@router.get("/{locomotive_id}/health", response_model=HealthIndex)
async def get_locomotive_health(locomotive_id: str, analytics: Analytics):
    """Get the current health index for a locomotive."""
    try:
        data = await analytics.get_current_health(locomotive_id)
    except Exception as exc:
        if "NOT_FOUND" in str(exc):
            raise HTTPException(status_code=404, detail="No telemetry data for this locomotive") from exc
        raise
    return _dict_to_health_index(data)


@router.get("/{locomotive_id}/health/at", response_model=HealthIndex)
async def get_locomotive_health_at(
    locomotive_id: str,
    analytics: Analytics,
    at: datetime = Query(..., description="Point in time (ISO 8601)"),
):
    """Get the health index at a specific point in time (replay)."""
    try:
        data = await analytics.get_health_at(locomotive_id, at.isoformat())
    except Exception as exc:
        if "NOT_FOUND" in str(exc):
            raise HTTPException(status_code=404, detail="No health data at this time") from exc
        raise
    return _dict_to_health_index(data)


def _dict_to_health_index(d: dict) -> HealthIndex:
    """Convert gRPC response dict to HealthIndex Pydantic model."""
    return HealthIndex(
        locomotive_id=d["locomotive_id"],
        locomotive_type=d.get("locomotive_type", ""),
        overall_score=d["overall_score"],
        category=d["category"],
        top_factors=[HealthFactor(**f) for f in d.get("top_factors", [])],
        damage_penalty=d.get("damage_penalty", 0.0),
        calculated_at=d.get("calculated_at", ""),
    )
