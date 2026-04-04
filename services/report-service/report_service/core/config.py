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

    # --- TimescaleDB / PostgreSQL ---
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "telemetry"
    db_password: str = "changeme"
    db_name: str = "locomotive_telemetry"
    db_pool_min: int = 5
    db_pool_max: int = 30  # read-heavy workload

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    # --- Domain ---
    report_retention_days: int = 90


@lru_cache
def get_settings() -> ReportSettings:
    return ReportSettings()
