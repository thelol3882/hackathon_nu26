from fastapi import APIRouter

from api_gateway.api.dependencies import DbSession
from shared.schemas.locomotive import LocomotiveCreate, LocomotiveRead

router = APIRouter()


@router.get("/")
async def list_locomotives(db: DbSession, offset: int = 0, limit: int = 50):
    """List all registered locomotives."""
    # TODO: implement
    return []


@router.post("/", status_code=201)
async def create_locomotive(data: LocomotiveCreate, db: DbSession):
    """Register a new locomotive."""
    # TODO: implement
    return {"status": "created"}


@router.get("/{locomotive_id}")
async def get_locomotive(locomotive_id: str, db: DbSession):
    """Get a single locomotive by ID."""
    # TODO: implement
    return {}
