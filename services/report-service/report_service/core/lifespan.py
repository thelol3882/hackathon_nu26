from contextlib import asynccontextmanager

from fastapi import FastAPI

from report_service.core.database import close_db_pool, init_db_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db_pool()
    yield
    await close_db_pool()
