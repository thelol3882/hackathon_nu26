# ---- Stage 1: Builder ----
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim AS builder

WORKDIR /build

# Copy dependency manifests first (cache-friendly layer)
COPY shared/pyproject.toml /build/shared/pyproject.toml
COPY shared/shared/ /build/shared/shared/
COPY services/report-service/pyproject.toml /build/pyproject.toml

# Compile pinned requirements from pyproject.toml (exclude local 'shared')
RUN uv pip compile pyproject.toml \
    --no-emit-package shared \
    --output-file requirements.txt

# Install dependencies into system Python
RUN uv pip install --system --no-cache -r requirements.txt \
    && uv pip install --system --no-cache ./shared/

# Copy service source
COPY services/report-service/ /build/app/

# ---- Stage 2: Runtime ----
FROM python:3.13-slim-bookworm

RUN groupadd -r app && useradd -r -g app -d /app -s /sbin/nologin app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin/uvicorn /usr/local/bin/uvicorn

WORKDIR /app
COPY --from=builder /build/app/ .

USER app

EXPOSE 8002

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
