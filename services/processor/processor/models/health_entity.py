import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from processor.models.base import Base


class HealthSnapshotRecord(Base):
    """Health index snapshot stored after each telemetry batch."""

    __tablename__ = "health_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    locomotive_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    locomotive_type: Mapped[str] = mapped_column(String(10), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False)      # 0–100
    category: Mapped[str] = mapped_column(String(20), nullable=False)  # Норма/Внимание/Критично
    # top_factors: list of HealthFactor dicts (up to 5)
    top_factors: Mapped[dict] = mapped_column(JSONB, nullable=False, default=list)
    damage_penalty: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
