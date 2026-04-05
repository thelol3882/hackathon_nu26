from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class WsServerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="WS_SERVER_",
        case_sensitive=False,
    )

    app_name: str = "locomotive-ws-server"
    debug: bool = False

    # Redis only — NO database connection
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_db: int = 0

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    # WS limits — can be higher since this server does ONLY WS
    max_connections: int = 500


@lru_cache
def get_settings() -> WsServerSettings:
    return WsServerSettings()
