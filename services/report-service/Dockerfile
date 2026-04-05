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
COPY services/report-service/pyproject.toml ./services/report-service/pyproject.toml

# Install dependencies only (cached layer)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-workspace --package report-service

COPY services/report-service/ ./services/report-service/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable --package report-service

# ---- Stage 2: Runtime ----
FROM python:3.13-slim-bookworm

RUN groupadd -g 1001 app && \
    useradd -u 1001 -g app -m -d /app -s /bin/false app

WORKDIR /app

COPY --from=builder --chown=app:app /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"

COPY --chown=app:app services/report-service/ /app/

USER app

EXPOSE 8002

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
