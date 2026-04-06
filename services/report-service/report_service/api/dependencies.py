from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from report_service.core.config import ReportSettings, get_settings
from report_service.core.database import get_db_session
from shared.grpc_client import AnalyticsClient

Settings = Annotated[ReportSettings, Depends(get_settings)]

DbSession = Annotated[AsyncSession, Depends(get_db_session)]


def _get_analytics(request: Request) -> AnalyticsClient:
    return request.app.state.analytics


Analytics = Annotated[AnalyticsClient, Depends(_get_analytics)]
