from fastapi import APIRouter
from pydantic import BaseModel

from api_gateway.api.dependencies import DbSession, Redis
from api_gateway.services.health_service import (
    ThresholdConfig,
    WeightConfig,
    list_thresholds,
    list_weights,
    update_threshold,
    update_weight,
)

router = APIRouter()


class ThresholdUpdate(BaseModel):
    min_value: float
    max_value: float


class WeightUpdate(BaseModel):
    weight: float


@router.get("/thresholds", response_model=list[ThresholdConfig])
async def get_thresholds(db: DbSession):
    return await list_thresholds(db)


@router.put("/thresholds/{sensor_type}", response_model=ThresholdConfig)
async def put_threshold(sensor_type: str, body: ThresholdUpdate, db: DbSession, redis: Redis):
    """Update threshold for a sensor type. Changes apply immediately."""
    return await update_threshold(db, redis, sensor_type, body.min_value, body.max_value)


@router.get("/weights", response_model=list[WeightConfig])
async def get_weights(db: DbSession):
    return await list_weights(db)


@router.put("/weights/{sensor_type}", response_model=WeightConfig)
async def put_weight(sensor_type: str, body: WeightUpdate, db: DbSession, redis: Redis):
    """Update weight for a sensor type. Changes apply immediately."""
    return await update_weight(db, redis, sensor_type, body.weight)
