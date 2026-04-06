"""ORM model for health index snapshots."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from analytics.models.base import Base
from shared.utils import generate_id


class HealthSnapshotRecord(Base):
    __tablename__ = "health_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=generate_id)
    locomotive_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    locomotive_type: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    category: Mapped[str] = mapped_column(Text, nullable=False)
    top_factors: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    damage_penalty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
