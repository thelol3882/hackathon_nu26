"""Lifespan is a no-op — infrastructure init is handled in main.py.

This module exists only because existing code may import from it.
The actual startup/shutdown logic lives in main.py which orchestrates
gRPC + HTTP + RabbitMQ concurrently.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
