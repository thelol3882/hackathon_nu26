import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from processor.models.base import Base


class TelemetryRecord(Base):
    """One sensor reading row in the TimescaleDB hypertable raw_telemetry."""

    __tablename__ = "raw_telemetry"

    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    locomotive_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True
    )
    locomotive_type: Mapped[str] = mapped_column(String(10), nullable=False)
    sensor_type: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    # filtered_value: EMA-smoothed value stored alongside raw
    filtered_value: Mapped[float] = mapped_column(Float, nullable=False)
    unit: Mapped[str] = mapped_column(String(20), nullable=False)
    sample_rate_hz: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
