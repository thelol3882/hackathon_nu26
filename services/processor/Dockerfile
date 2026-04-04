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
COPY services/processor/pyproject.toml ./services/processor/pyproject.toml

# Install dependencies only (cached layer)
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-workspace --package processor

# Copy service source and install project
COPY services/processor/ ./services/processor/

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-editable --package processor

# ---- Stage 2: Runtime ----
FROM python:3.13-slim-bookworm

RUN groupadd -g 1001 app && \
    useradd -u 1001 -g app -m -d /app -s /bin/false app

WORKDIR /app

COPY --from=builder --chown=app:app /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"

# Copy service source (for main.py entrypoint)
COPY --chown=app:app services/processor/ /app/

USER app

EXPOSE 8001

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001"]
