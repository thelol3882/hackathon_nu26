# syntax=docker/dockerfile:1

# ---- Stage 1: Builder ----
FROM python:3.13-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1

COPY pyproject.toml uv.lock ./
COPY shared/ ./shared/
COPY services/ws-server/pyproject.toml ./services/ws-server/pyproject.toml

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-workspace --package ws-server

COPY services/ws-server/ ./services/ws-server/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable --package ws-server

# ---- Stage 2: Runtime ----
FROM python:3.13-slim-bookworm

RUN groupadd -g 1001 app && \
    useradd -u 1001 -g app -m -d /app -s /bin/false app

WORKDIR /app

COPY --from=builder --chown=app:app /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"

COPY --chown=app:app services/ws-server/ /app/

USER app

EXPOSE 8010

# Single worker is optimal for WebSocket:
# connections are long-lived and stateful, asyncio handles thousands.
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8010", "--workers", "1"]
