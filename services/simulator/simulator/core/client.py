import asyncio

import httpx

from shared.observability import get_logger
from simulator.core.config import settings

logger = get_logger(__name__)

_client: httpx.AsyncClient | None = None

MAX_RETRIES = 3
BACKOFF_BASE = 0.5  # seconds


async def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            base_url=settings.processor_url,
            timeout=5.0,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )
    return _client


async def post_batch(readings_json: list[dict]) -> dict | None:
    """POST a batch of TelemetryReading dicts to the processor. Returns response or None on failure."""
    client = await get_client()
    for attempt in range(MAX_RETRIES):
        try:
            resp = await client.post("/telemetry/ingest/batch", json=readings_json)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 503):
                wait = BACKOFF_BASE * (2**attempt)
                logger.warning("Processor returned %d, backing off %.1fs", resp.status_code, wait)
                await asyncio.sleep(wait)
                continue
            logger.error("Processor returned %d: %s", resp.status_code, resp.text[:200])
            return None
        except httpx.HTTPError as exc:
            wait = BACKOFF_BASE * (2**attempt)
            logger.warning("HTTP error (attempt %d): %s, retrying in %.1fs", attempt + 1, exc, wait)
            await asyncio.sleep(wait)
    logger.error("All %d retries exhausted for batch POST", MAX_RETRIES)
    return None


async def close_client() -> None:
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
