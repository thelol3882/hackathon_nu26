from typing import Annotated

import redis.asyncio as redis
from fastapi import Depends

from processor.core.config import ProcessorSettings, get_settings
from processor.core.redis_client import get_redis

Settings = Annotated[ProcessorSettings, Depends(get_settings)]
Redis = Annotated[redis.Redis, Depends(get_redis)]
