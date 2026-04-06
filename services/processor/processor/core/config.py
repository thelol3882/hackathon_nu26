from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class ProcessorSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PROCESSOR_",
        case_sensitive=False,
    )

    app_name: str = "locomotive-processor"
    debug: bool = False

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    telemetry_batch_size: int = 100
    alert_cooldown_seconds: int = 30


@lru_cache
def get_settings() -> ProcessorSettings:
    return ProcessorSettings()
