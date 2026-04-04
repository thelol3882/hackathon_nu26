import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from api_gateway.models.base import Base
from shared.utils import generate_id


class Locomotive(Base):
    __tablename__ = "locomotives"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=generate_id
    )
    serial_number: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    manufacturer: Mapped[str] = mapped_column(String(200), nullable=False)
    year_manufactured: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
