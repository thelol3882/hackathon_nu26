"""Wire format: msgpack binary serialization for all inter-service messaging.

All pub/sub payloads and WebSocket frames use msgpack for compact, efficient encoding.
"""

from __future__ import annotations

import ormsgpack


def encode(data: dict) -> bytes:
    """Serialize a dict to bytes using msgpack."""
    return ormsgpack.packb(data)


def decode(raw: bytes) -> dict:
    """Deserialize bytes from msgpack."""
    return ormsgpack.unpackb(raw)


def is_binary() -> bool:
    """Always True — wire format is binary (msgpack)."""
    return True
