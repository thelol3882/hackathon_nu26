.PHONY: test test-processor test-api-gateway test-report-service

test: test-processor test-api-gateway test-report-service

test-processor:
	cd services/processor && python -m pytest tests/ -v

test-api-gateway:
	cd services/api-gateway && python -m pytest tests/ -v

test-report-service:
	cd services/report-service && python -m pytest tests/ -v
