# LoanFlow developer tasks. Run `make help` for the list.
# On Windows, run these from Git Bash, or use the raw commands in CLAUDE.md.

.DEFAULT_GOAL := help
COMPOSE := docker compose

.PHONY: help up down logs build ps test test-api test-web fmt lint typecheck migrate revision upgrade seed shell-api shell-db

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

up: ## Start the full stack
	$(COMPOSE) up --build

down: ## Stop the stack
	$(COMPOSE) down

logs: ## Tail logs
	$(COMPOSE) logs -f

ps: ## Show running services
	$(COMPOSE) ps

build: ## Rebuild images
	$(COMPOSE) build

test: test-api test-web ## Run all tests

test-api: ## Run backend tests
	$(COMPOSE) run --rm api pytest -q

test-web: ## Run frontend tests
	$(COMPOSE) run --rm web sh -c "npm install && npm test -- --run"

fmt: ## Format all code
	$(COMPOSE) run --rm api ruff format .
	$(COMPOSE) run --rm web sh -c "npm install && npm run fmt"

lint: ## Lint all code
	$(COMPOSE) run --rm api ruff check .
	$(COMPOSE) run --rm web sh -c "npm install && npm run lint"

typecheck: ## Type-check backend and frontend
	$(COMPOSE) run --rm api mypy app
	$(COMPOSE) run --rm web sh -c "npm install && npm run typecheck"

migrate: revision upgrade ## Create + apply a migration: make migrate m="message"

revision: ## Autogenerate a migration: make revision m="message"
	$(COMPOSE) run --rm api alembic revision --autogenerate -m "$(m)"

upgrade: ## Apply migrations
	$(COMPOSE) run --rm api alembic upgrade head

seed: ## Load demo data
	$(COMPOSE) run --rm api python -m app.seed_demo

shell-api: ## Shell into the api container
	$(COMPOSE) run --rm api bash

shell-db: ## psql into the database
	$(COMPOSE) exec db psql -U loanflow -d loanflow
