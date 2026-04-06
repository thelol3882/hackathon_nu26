from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from shared.enums import SensorType


class ComponentHealth(BaseModel):
    """Historical batch score (0.0–1.0) used by report-service."""

    sensor_type: SensorType
    score: float
    latest_value: float
    unit: str


class HealthFactor(BaseModel):
    """Top-N contributing factor in real-time HI calculation."""

    sensor_type: str
    value: float
    unit: str
    penalty: float
    contribution_pct: float  # share of total penalty (0–100 %)
    deviation_pct: float  # distance from nominal toward critical (0–100 %)


class HealthIndex(BaseModel):
    """Real-time health index emitted by processor (0–100 scale)."""

    locomotive_id: UUID
    locomotive_type: str
    overall_score: float  # 100 = perfect
    category: str  # "Норма" | "Внимание" | "Критично" (Normal | Warning | Critical)
    top_factors: list[HealthFactor]  # up to 5 worst sensors
    damage_penalty: float  # accumulated Montsinger aging penalty
    calculated_at: datetime


class HealthSnapshot(BaseModel):
    """Lightweight streaming snapshot (no factor detail)."""

    locomotive_id: UUID
    overall_score: float
    category: str
    calculated_at: datetime
