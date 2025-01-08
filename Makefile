# Makefile

# ------------------------ #
#          Serve           #
# ------------------------ #

start:
	@if [ -f env.sh ]; then source env.sh; fi; fastapi dev 'www/main.py' --host localhost --port 8080
.PHONY: start

start-docker-dynamodb:
	@docker kill www-db || true
	@docker rm www-db || true
	@docker run --name www-db -d -p 8000:8000 amazon/dynamodb-local
.PHONY: start-docker-dynamodb

start-docker-backend:
	@docker kill www-backend || true
	@docker rm www-backend || true
	@docker build -t www-backend .
	@docker run --name www-backend -d -p 8080:8080 www-backend
.PHONY: start-docker-backend

start-docker-localstack:
	@docker kill www-localstack || true
	@docker rm www-localstack || true
	@docker run -d --name www-localstack -p 4566:4566 -p 4571:4571 localstack/localstack
.PHONY: start-docker-localstack

# ------------------------ #
#        Install           #
# ------------------------ #

install:
	@pip install -e '[.dev]'
.PHONY: install

# ------------------------ #
#      Code Formatting     #
# ------------------------ #

format:
	@black www tests
	@ruff check --fix www tests
.PHONY: format

# ------------------------ #
#       Static Checks      #
# ------------------------ #

lint:
	@black --diff --check www tests
	@ruff check www tests
	@mypy --install-types --non-interactive www tests
.PHONY: lint

# ------------------------ #
#        Unit tests        #
# ------------------------ #

test:
	@python -m pytest
.PHONY: test-backend
