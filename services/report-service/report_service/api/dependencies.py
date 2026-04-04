from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from report_service.core.config import ReportSettings, get_settings
from report_service.core.database import get_db_session

Settings = Annotated[ReportSettings, Depends(get_settings)]
DbSession = Annotated[AsyncSession, Depends(get_db_session)]
