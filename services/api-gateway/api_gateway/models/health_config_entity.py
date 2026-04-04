from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from api_gateway.models.base import Base


class HealthThreshold(Base):
    __tablename__ = "health_thresholds"

    sensor_type: Mapped[str] = mapped_column(String(50), primary_key=True)
    min_value: Mapped[float] = mapped_column(Float, nullable=False)
    max_value: Mapped[float] = mapped_column(Float, nullable=False)


class HealthWeight(Base):
    __tablename__ = "health_weights"

    sensor_type: Mapped[str] = mapped_column(String(50), primary_key=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
