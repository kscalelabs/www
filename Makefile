# Makefile

ENV_VARS = \
	ENVIRONMENT=local \
	AWS_REGION=us-east-1 \
	AWS_DEFAULT_REGION=us-east-1 \
	AWS_ACCESS_KEY_ID=test \
	AWS_SECRET_ACCESS_KEY=test \
	AWS_ENDPOINT_URL=http://localhost:4566

start:
	$(ENV_VARS) fastapi dev 'www/main.py' --host localhost --port 8080
.PHONY: start

start-localstack:
	@docker compose --file docker/docker-compose-localstack.yml down --remove-orphans
	@docker rm -f www-localstack 2>/dev/null || true
	@docker compose --file docker/docker-compose-localstack.yml up -d localstack --force-recreate
.PHONY: start-localstack

create-db:
	$(ENV_VARS) python -m scripts.create_db --s3 --db
.PHONY: create-db

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
