"""Async RabbitMQ consumer for report generation jobs."""

from __future__ import annotations

from collections.abc import Callable

import aio_pika

from report_service.core.config import get_settings
from shared.log_codes import INFRA_RABBITMQ_CLOSED, INFRA_RABBITMQ_CONNECTED, REPORT_CONSUMER_STARTED
from shared.observability import get_logger

logger = get_logger(__name__)

REPORT_QUEUE = "report.generate"

_connection: aio_pika.abc.AbstractRobustConnection | None = None
_channel: aio_pika.abc.AbstractChannel | None = None
_queue: aio_pika.abc.AbstractQueue | None = None


async def init_rabbitmq() -> None:
    global _connection, _channel, _queue
    settings = get_settings()
    _connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    _channel = await _connection.channel()
    await _channel.set_qos(prefetch_count=1)
    _queue = await _channel.declare_queue(REPORT_QUEUE, durable=True)
    logger.info("RabbitMQ connected", code=INFRA_RABBITMQ_CONNECTED, queue=REPORT_QUEUE)


async def start_consuming(on_message: Callable) -> None:
    """Start consuming messages from the report queue. Blocks until cancelled."""
    if _queue is None:
        raise RuntimeError("RabbitMQ not initialized. Call init_rabbitmq() first.")
    await _queue.consume(on_message)
    logger.info("Report consumer started", code=REPORT_CONSUMER_STARTED, queue=REPORT_QUEUE)


async def close_rabbitmq() -> None:
    global _connection, _channel, _queue
    if _channel:
        await _channel.close()
        _channel = None
    if _connection:
        await _connection.close()
        _connection = None
    _queue = None
    logger.info("RabbitMQ closed", code=INFRA_RABBITMQ_CLOSED)
