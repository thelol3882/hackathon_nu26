# Import all ORM models here so SQLAlchemy metadata.create_all can discover them.
from db_writer.models.alert_entity import AlertRecord  # noqa: F401
from db_writer.models.health_entity import HealthSnapshotRecord  # noqa: F401
from db_writer.models.telemetry_entity import TelemetryRecord  # noqa: F401
