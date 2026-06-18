PYTHON ?= python
BACKEND_DIR := backend
FRONTEND_DIR := frontend
UV_CACHE_DIR := $(CURDIR)/.uv-cache

.PHONY: bootstrap dev down logs migrate backend-test backend-lint backend-typecheck frontend-dev frontend-test frontend-lint frontend-typecheck format check

bootstrap:
	UV_CACHE_DIR=$(UV_CACHE_DIR) $(PYTHON) -m uv sync --project $(BACKEND_DIR) --group dev
	cd $(FRONTEND_DIR) && npm install

dev:
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f --tail=200

migrate:
	docker compose run --rm api python -m alembic -c /app/alembic.ini upgrade head

backend-test:
	cd $(BACKEND_DIR) && UV_CACHE_DIR=$(UV_CACHE_DIR) $(PYTHON) -m uv run pytest

backend-lint:
	cd $(BACKEND_DIR) && UV_CACHE_DIR=$(UV_CACHE_DIR) $(PYTHON) -m uv run ruff check .

backend-typecheck:
	cd $(BACKEND_DIR) && UV_CACHE_DIR=$(UV_CACHE_DIR) $(PYTHON) -m uv run mypy app

frontend-dev:
	cd $(FRONTEND_DIR) && npm run dev

frontend-test:
	cd $(FRONTEND_DIR) && npm test

frontend-lint:
	cd $(FRONTEND_DIR) && npm run lint

frontend-typecheck:
	cd $(FRONTEND_DIR) && npm run typecheck

format:
	cd $(BACKEND_DIR) && UV_CACHE_DIR=$(UV_CACHE_DIR) $(PYTHON) -m uv run ruff format .
	cd $(FRONTEND_DIR) && npm run format

check: backend-lint backend-typecheck backend-test frontend-lint frontend-typecheck frontend-test
