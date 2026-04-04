from typing import Annotated

import redis.asyncio as redis
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api_gateway.core.config import GatewaySettings, get_settings
from api_gateway.core.database import get_db_session
from api_gateway.core.redis_client import get_redis

Settings = Annotated[GatewaySettings, Depends(get_settings)]
DbSession = Annotated[AsyncSession, Depends(get_db_session)]
Redis = Annotated[redis.Redis, Depends(get_redis)]
