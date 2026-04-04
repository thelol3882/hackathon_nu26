.PHONY: test test-processor test-api-gateway test-report-service \
       up down build logs restart \
       up-infra up-services up-simulator \
       ps status clean env migrate

# ──────────────────────────────────────
#  Full stack
# ──────────────────────────────────────
up: env
	docker compose up -d --build

down:
	docker compose down

restart: down up

build:
	docker compose build

logs:
	docker compose logs -f

ps:
	docker compose ps

# ──────────────────────────────────────
#  Selective startup
# ──────────────────────────────────────
up-infra:
	docker compose up -d timescaledb redis rabbitmq jaeger

up-services: up-infra
	docker compose up -d --build processor api-gateway report-service nginx

up-simulator:
	docker compose up -d --build simulator

# ──────────────────────────────────────
#  Service logs (individual)
# ──────────────────────────────────────
logs-api:
	docker compose logs -f api-gateway

logs-processor:
	docker compose logs -f processor

logs-reports:
	docker compose logs -f report-service

logs-simulator:
	docker compose logs -f simulator

# ──────────────────────────────────────
#  Health / status
# ──────────────────────────────────────
status:
	@echo "=== API Gateway ===" && curl -sf http://localhost/api/health && echo || echo "DOWN"
	@echo "=== Processor ===" && docker compose exec processor curl -sf http://localhost:8001/health && echo || echo "DOWN"
	@echo "=== RabbitMQ ===" && curl -sf http://localhost:15672 > /dev/null && echo "OK" || echo "DOWN"
	@echo "=== Jaeger ===" && curl -sf http://localhost:16686 > /dev/null && echo "OK" || echo "DOWN"

# ──────────────────────────────────────
#  Environment
# ──────────────────────────────────────
env:
	@test -f .env || (cp .env.example .env && echo "Created .env from .env.example")

# ──────────────────────────────────────
#  Cleanup
# ──────────────────────────────────────
clean: down
	docker compose down -v --remove-orphans
	docker image prune -f

# ──────────────────────────────────────
#  Tests
# ──────────────────────────────────────
test: test-processor test-api-gateway test-report-service

test-processor:
	cd services/processor && python -m pytest tests/ -v

test-api-gateway:
	cd services/api-gateway && python -m pytest tests/ -v

test-report-service:
	cd services/report-service && python -m pytest tests/ -v
