# syntax=docker/dockerfile:1

# ---- Stage 1: Builder ----
FROM python:3.13-slim-bookworm AS builder

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /uvx /bin/

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1

# Copy workspace root manifests + shared package
COPY pyproject.toml uv.lock ./
COPY shared/ ./shared/
COPY services/analytics-service/pyproject.toml ./services/analytics-service/pyproject.toml

# Install dependencies only (cached layer)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-workspace --package analytics-service

# Copy service source and install project
COPY services/analytics-service/ ./services/analytics-service/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable --package analytics-service

# ---- Stage 2: Runtime ----
FROM python:3.13-slim-bookworm

RUN groupadd -g 1001 app && \
    useradd -u 1001 -g app -m -d /app -s /bin/false app

WORKDIR /app

COPY --from=builder --chown=app:app /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"

COPY --chown=app:app services/analytics-service/ /app/

USER app

# gRPC on 50051, HTTP metrics on 8020
EXPOSE 50051 8020

CMD ["python", "main.py"]
