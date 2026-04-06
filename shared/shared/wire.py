"""Wire format: msgpack for all pub/sub and WebSocket payloads."""

from __future__ import annotations

import ormsgpack


def encode(data: dict) -> bytes:
    return ormsgpack.packb(data)


def decode(raw: bytes) -> dict:
    return ormsgpack.unpackb(raw)


def is_binary() -> bool:
    return True
