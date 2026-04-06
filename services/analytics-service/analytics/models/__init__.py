# Import all ORM models so SQLAlchemy metadata and Alembic can discover them.
from analytics.models.alert_entity import AlertRecord  # noqa: F401
from analytics.models.health_entity import HealthSnapshotRecord  # noqa: F401
from analytics.models.telemetry_entity import TelemetryRecord  # noqa: F401
