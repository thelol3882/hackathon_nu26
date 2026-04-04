"""Scalable WebSocket connection manager with fan-out and backpressure.

One Redis pub/sub subscription per channel is shared across all WebSocket
clients subscribed to that channel.  Each client gets its own bounded
asyncio.Queue so a slow consumer never blocks the Redis listener or
other clients.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

import redis.asyncio as redis
from fastapi import WebSocket
from starlette.websockets import WebSocketState

from shared.log_codes import (
    INFRA_REDIS_RECONNECTING,
    WS_CONNECTED,
    WS_DISCONNECTED,
    WS_LIMIT_REACHED,
    WS_RELAY_ERROR,
    WS_RELAY_STARTED,
    WS_STALE_REMOVED,
)
from shared.observability import get_logger
from shared.wire import decode as wire_decode
from shared.wire import is_binary as wire_is_binary

logger = get_logger(__name__)

_QUEUE_MAX = 64
_HEARTBEAT_INTERVAL = 30  # seconds
_RECONNECT_BASE = 1.0
_RECONNECT_MAX = 30.0


@dataclass
class _ClientSlot:
    """Per-client state inside a ChannelRelay."""

    queue: asyncio.Queue[bytes] = field(default_factory=lambda: asyncio.Queue(maxsize=_QUEUE_MAX))
    sender_task: asyncio.Task | None = None
    filter_loco_id: str | None = None  # if set, only forward messages matching this loco


class _ChannelRelay:
    """Manages a single Redis pub/sub channel shared by N WebSocket clients."""

    def __init__(self, channel: str, redis_client: redis.Redis) -> None:
        self.channel = channel
        self._redis = redis_client
        self._clients: dict[int, _ClientSlot] = {}  # id(ws) -> slot
        self._ws_map: dict[int, WebSocket] = {}
        self._listener_task: asyncio.Task | None = None
        self._lock = asyncio.Lock()

    @property
    def client_count(self) -> int:
        return len(self._clients)

    async def add_client(
        self,
        ws: WebSocket,
        filter_loco_id: str | None = None,
    ) -> None:
        async with self._lock:
            ws_id = id(ws)
            slot = _ClientSlot(filter_loco_id=filter_loco_id)
            slot.sender_task = asyncio.create_task(
                self._sender_loop(ws, slot.queue),
                name=f"ws-sender-{ws_id}",
            )
            self._clients[ws_id] = slot
            self._ws_map[ws_id] = ws

            if self._listener_task is None or self._listener_task.done():
                self._listener_task = asyncio.create_task(self._listener_loop(), name=f"redis-listener-{self.channel}")

    async def remove_client(self, ws: WebSocket) -> int:
        """Remove client, return remaining count."""
        async with self._lock:
            ws_id = id(ws)
            slot = self._clients.pop(ws_id, None)
            self._ws_map.pop(ws_id, None)
            if slot and slot.sender_task:
                slot.sender_task.cancel()

            remaining = len(self._clients)
            if remaining == 0 and self._listener_task:
                self._listener_task.cancel()
                self._listener_task = None
            return remaining

    async def shutdown(self) -> None:
        async with self._lock:
            if self._listener_task:
                self._listener_task.cancel()
                self._listener_task = None
            for slot in self._clients.values():
                if slot.sender_task:
                    slot.sender_task.cancel()
            self._clients.clear()
            self._ws_map.clear()

    # --- internal loops ---

    async def _listener_loop(self) -> None:
        """Subscribe to Redis and distribute messages to client queues."""
        backoff = _RECONNECT_BASE
        while True:
            pubsub = self._redis.pubsub()
            try:
                await pubsub.subscribe(self.channel)
                backoff = _RECONNECT_BASE
                logger.info("Redis relay started", code=WS_RELAY_STARTED, channel=self.channel)
                async for message in pubsub.listen():
                    if message["type"] != b"message":
                        continue
                    data: bytes = message["data"]
                    async with self._lock:
                        for slot in self._clients.values():
                            if slot.filter_loco_id:
                                try:
                                    parsed = wire_decode(data)
                                    msg_loco = str(parsed.get("locomotive_id", ""))
                                    if msg_loco != slot.filter_loco_id:
                                        continue
                                except Exception:
                                    pass
                            # backpressure: drop oldest if full
                            if slot.queue.full():
                                try:
                                    slot.queue.get_nowait()
                                except asyncio.QueueEmpty:
                                    pass
                            try:
                                slot.queue.put_nowait(data)
                            except asyncio.QueueFull:
                                pass
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception(
                    "Redis relay error, reconnecting",
                    code=INFRA_REDIS_RECONNECTING,
                    channel=self.channel,
                    backoff_s=backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, _RECONNECT_MAX)
            finally:
                try:
                    await pubsub.unsubscribe()
                    await pubsub.aclose()
                except Exception:
                    pass

    @staticmethod
    async def _sender_loop(ws: WebSocket, queue: asyncio.Queue[bytes]) -> None:
        """Read from the client's queue and send over WebSocket.

        Wire format is global: msgpack → send_bytes (zero-copy from Redis),
        json → decode to str → send_text.
        """
        binary = wire_is_binary()
        try:
            while True:
                data = await queue.get()
                if binary:
                    await ws.send_bytes(data)
                else:
                    await ws.send_text(data.decode())
        except asyncio.CancelledError:
            pass
        except Exception:
            logger.debug("Sender loop ended", code=WS_RELAY_ERROR, ws_id=id(ws))


class ConnectionManager:
    """Top-level manager: tracks all connections and channel relays."""

    def __init__(self, redis_client: redis.Redis, max_connections: int = 100) -> None:
        self._redis = redis_client
        self._max_connections = max_connections
        self._relays: dict[str, _ChannelRelay] = {}
        self._connections: dict[int, set[str]] = {}  # id(ws) -> set of channel keys
        self._ws_refs: dict[int, WebSocket] = {}
        self._lock = asyncio.Lock()
        self._heartbeat_task: asyncio.Task | None = None

    @property
    def active_connections(self) -> int:
        return len(self._connections)

    async def start(self) -> None:
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop(), name="ws-heartbeat")

    async def accept(self, ws: WebSocket) -> bool:
        """Accept a WebSocket connection. Returns False if over limit."""
        async with self._lock:
            if len(self._connections) >= self._max_connections:
                logger.warning(
                    "WebSocket connection limit reached",
                    code=WS_LIMIT_REACHED,
                    active=len(self._connections),
                    max=self._max_connections,
                )
                await ws.close(code=1013, reason="Server too busy")
                return False
            ws_id = id(ws)
            self._connections[ws_id] = set()
            self._ws_refs[ws_id] = ws
        await ws.accept()
        logger.info(
            "WebSocket connected",
            code=WS_CONNECTED,
            active=self.active_connections,
        )
        return True

    async def subscribe(
        self,
        ws: WebSocket,
        channel: str,
        *,
        filter_loco_id: str | None = None,
    ) -> None:
        """Subscribe a client to a Redis channel (shared relay)."""
        async with self._lock:
            ws_id = id(ws)
            if channel not in self._relays:
                self._relays[channel] = _ChannelRelay(channel, self._redis)
            self._connections.setdefault(ws_id, set()).add(channel)

        await self._relays[channel].add_client(ws, filter_loco_id=filter_loco_id)

    async def disconnect(self, ws: WebSocket) -> None:
        """Remove a client from all channels and tracking."""
        async with self._lock:
            ws_id = id(ws)
            channels = self._connections.pop(ws_id, set())
            self._ws_refs.pop(ws_id, None)

        for ch in channels:
            relay = self._relays.get(ch)
            if relay:
                remaining = await relay.remove_client(ws)
                if remaining == 0:
                    async with self._lock:
                        self._relays.pop(ch, None)

        logger.info(
            "WebSocket disconnected",
            code=WS_DISCONNECTED,
            active=self.active_connections,
        )

        # best-effort close
        try:
            if ws.client_state == WebSocketState.CONNECTED:
                await ws.close()
        except Exception:
            pass

    async def shutdown(self) -> None:
        """Graceful shutdown: close all connections and relays."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            self._heartbeat_task = None

        async with self._lock:
            relays = list(self._relays.values())
            ws_list = list(self._ws_refs.values())
            self._relays.clear()
            self._connections.clear()
            self._ws_refs.clear()

        for relay in relays:
            await relay.shutdown()

        for ws in ws_list:
            try:
                if ws.client_state == WebSocketState.CONNECTED:
                    await ws.close(code=1001, reason="Server shutting down")
            except Exception:
                pass

    async def _heartbeat_loop(self) -> None:
        """Periodically ping all connections, remove stale ones."""
        while True:
            try:
                await asyncio.sleep(_HEARTBEAT_INTERVAL)
                async with self._lock:
                    ws_list = list(self._ws_refs.values())

                stale: list[WebSocket] = []
                for ws in ws_list:
                    try:
                        await ws.send_json({"type": "ping"})
                    except Exception:
                        stale.append(ws)

                for ws in stale:
                    logger.info("Removing stale connection", code=WS_STALE_REMOVED)
                    await self.disconnect(ws)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Heartbeat error")
