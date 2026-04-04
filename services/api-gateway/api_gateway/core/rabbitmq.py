"""Async RabbitMQ connection and publishing utilities using aio-pika."""

from __future__ import annotations

import json

import aio_pika
from aio_pika import DeliveryMode, Message

from api_gateway.core.config import get_settings
from shared.log_codes import INFRA_RABBITMQ_CLOSED, INFRA_RABBITMQ_CONNECTED, REPORT_PUBLISHED
from shared.observability import get_logger

logger = get_logger(__name__)

REPORT_QUEUE = "report.generate"

_connection: aio_pika.abc.AbstractRobustConnection | None = None
_channel: aio_pika.abc.AbstractChannel | None = None


async def init_rabbitmq() -> None:
    global _connection, _channel
    settings = get_settings()
    _connection = await aio_pika.connect_robust(settings.rabbitmq_url)
    _channel = await _connection.channel()
    # Declare durable queue so messages survive broker restart
    await _channel.declare_queue(REPORT_QUEUE, durable=True)
    logger.info("RabbitMQ connected", code=INFRA_RABBITMQ_CONNECTED, queue=REPORT_QUEUE)


async def close_rabbitmq() -> None:
    global _connection, _channel
    if _channel:
        await _channel.close()
        _channel = None
    if _connection:
        await _connection.close()
        _connection = None
    logger.info("RabbitMQ closed", code=INFRA_RABBITMQ_CLOSED)


def get_channel() -> aio_pika.abc.AbstractChannel:
    if _channel is None:
        raise RuntimeError("RabbitMQ not initialized. Call init_rabbitmq() first.")
    return _channel


async def publish_report_job(payload: dict) -> None:
    channel = get_channel()
    message = Message(
        body=json.dumps(payload, default=str).encode(),
        delivery_mode=DeliveryMode.PERSISTENT,
        content_type="application/json",
    )
    await channel.default_exchange.publish(
        message,
        routing_key=REPORT_QUEUE,
    )
    logger.info("Report job published", code=REPORT_PUBLISHED, report_id=payload.get("report_id"))
