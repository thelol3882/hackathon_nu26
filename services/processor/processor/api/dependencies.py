from typing import Annotated

import redis.asyncio as redis
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from processor.core.config import ProcessorSettings, get_settings
from processor.core.database import get_db_session
from processor.core.redis_client import get_redis

Settings = Annotated[ProcessorSettings, Depends(get_settings)]
DbSession = Annotated[AsyncSession, Depends(get_db_session)]
Redis = Annotated[redis.Redis, Depends(get_redis)]
