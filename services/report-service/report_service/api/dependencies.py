from typing import Annotated

import asyncpg
from fastapi import Depends

from report_service.core.config import ReportSettings, get_settings
from report_service.core.database import get_db_pool

Settings = Annotated[ReportSettings, Depends(get_settings)]
DbPool = Annotated[asyncpg.Pool, Depends(get_db_pool)]
