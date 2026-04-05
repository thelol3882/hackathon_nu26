from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class ReportSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="REPORT_",
        case_sensitive=False,
    )

    # --- Application ---
    app_name: str = "locomotive-report-service"
    debug: bool = False

    # --- PostgreSQL (for generated_reports table only) ---
    db_host: str = "postgres"
    db_port: int = 5432
    db_user: str = "locomotive_app"
    db_password: str = "changeme"
    db_name: str = "locomotive_app"
    db_pool_min: int = 2
    db_pool_max: int = 10

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    # --- Analytics Service (gRPC) ---
    # Telemetry, alert, and health data comes via gRPC.
    # Report Service no longer connects to TimescaleDB directly.
    analytics_grpc_target: str = "analytics-service:50051"
    analytics_grpc_timeout: float = 30.0  # Reports can be heavy — longer timeout

    # --- RabbitMQ ---
    rabbitmq_url: str = "amqp://locomotive:changeme@rabbitmq:5672/"

    # --- Domain ---
    report_retention_days: int = 90


@lru_cache
def get_settings() -> ReportSettings:
    return ReportSettings()
