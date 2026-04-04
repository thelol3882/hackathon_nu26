# Import all ORM models here so Alembic autogenerate can discover them.
from processor.models.alert_entity import AlertRecord  # noqa: F401
from processor.models.health_entity import HealthSnapshotRecord  # noqa: F401
from processor.models.telemetry_entity import TelemetryRecord  # noqa: F401
