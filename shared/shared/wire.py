"""Wire format: global JSON ↔ msgpack switch for all inter-service messaging.

Set WIRE_FORMAT=msgpack to enable binary mode across all services.
Default: json (human-readable, good for local dev and debugging).

All pub/sub payloads go through encode/decode so the switch is transparent.
"""

from __future__ import annotations

import json
import os

import ormsgpack

WIRE_FORMAT: str = os.environ.get("WIRE_FORMAT", "json")


def encode(data: dict) -> bytes:
    """Serialize a dict to bytes using the configured wire format."""
    if WIRE_FORMAT == "msgpack":
        return ormsgpack.packb(data)
    return json.dumps(data, default=str).encode()


def decode(raw: bytes) -> dict:
    """Deserialize bytes to a dict using the configured wire format."""
    if WIRE_FORMAT == "msgpack":
        return ormsgpack.unpackb(raw)
    return json.loads(raw)


def is_binary() -> bool:
    """True if wire format is binary (msgpack). Used by WS sender to choose send_bytes vs send_text."""
    return WIRE_FORMAT == "msgpack"
