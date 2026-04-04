from typing import Annotated

import asyncpg
import redis.asyncio as redis
from fastapi import Depends

from api_gateway.core.config import GatewaySettings, get_settings
from api_gateway.core.database import get_db_pool
from api_gateway.core.redis_client import get_redis

Settings = Annotated[GatewaySettings, Depends(get_settings)]
DbPool = Annotated[asyncpg.Pool, Depends(get_db_pool)]
Redis = Annotated[redis.Redis, Depends(get_redis)]
