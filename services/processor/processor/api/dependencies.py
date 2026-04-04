from typing import Annotated

import asyncpg
import redis.asyncio as redis
from fastapi import Depends

from processor.core.config import ProcessorSettings, get_settings
from processor.core.database import get_db_pool
from processor.core.redis_client import get_redis

Settings = Annotated[ProcessorSettings, Depends(get_settings)]
DbPool = Annotated[asyncpg.Pool, Depends(get_db_pool)]
Redis = Annotated[redis.Redis, Depends(get_redis)]
