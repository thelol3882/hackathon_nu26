from fastapi import APIRouter

from api_gateway.api.dependencies import DbSession, Redis
from api_gateway.services import locomotive_service
from api_gateway.services.health_service import get_health_index
from shared.schemas.health import HealthIndex
from shared.schemas.locomotive import LocomotiveCreate, LocomotiveRead

router = APIRouter()


@router.get("/", response_model=list[LocomotiveRead])
async def list_locomotives(db: DbSession, offset: int = 0, limit: int = 50):
    """List all registered locomotives."""
    return await locomotive_service.list_locomotives(db, offset=offset, limit=limit)


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
