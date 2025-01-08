# Makefile

start:
	@if [ -f env.sh ]; then source env.sh; fi; fastapi dev 'www/main.py' --host localhost --port 8080
.PHONY: start

start-localstack:
	@docker kill www-localstack || true
	@docker rm www-localstack || true
	@docker run -d --name www-localstack -p 4566:4566 -p 4571:4571 localstack/localstack
.PHONY: start-docker-localstack

format:
	@black www tests
	@ruff check --fix www tests
.PHONY: format

lint:
	@black --diff --check www tests
	@ruff check www tests
	@mypy --install-types --non-interactive www tests
.PHONY: lint

test:
	@python -m pytest
.PHONY: test-backend
