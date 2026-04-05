from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from api_gateway.api.dependencies import AppSession, Redis, TsSession

router = APIRouter()


@router.get("/health")
async def health():
    """Liveness probe."""
    return {"status": "healthy"}


@router.get("/ready")
async def ready(app_db: AppSession, ts_db: TsSession, redis: Redis):
    """Readiness probe — checks both databases and Redis connectivity."""
    checks = {}
    try:
        await app_db.execute(text("SELECT 1"))
        checks["app_database"] = "ok"
    except Exception as e:
        checks["app_database"] = str(e)

    try:
        await ts_db.execute(text("SELECT 1"))
        checks["ts_database"] = "ok"
    except Exception as e:
        checks["ts_database"] = str(e)

    try:
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = str(e)

    all_ok = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={"status": "ready" if all_ok else "not_ready", "checks": checks},
    )
