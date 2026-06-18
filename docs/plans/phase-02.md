# Phase 2 Plan

## Scope

Phase 2 establishes the backend foundation for CodePilot: async PostgreSQL access, Alembic migrations, Redis, Celery, API conventions, dependency injection, and readiness checks. No domain authentication or repository entities are introduced yet.

## Goals

- Add async SQLAlchemy sessions and transaction helpers.
- Add a minimal Alembic migration that can upgrade and downgrade an empty database.
- Add Redis and Celery abstractions with safe JSON serialization.
- Add typed pagination, exception mapping, request-size limits, and trusted-host handling.
- Add dependency health checks for PostgreSQL, Redis, Qdrant, and Ollama.
- Add idempotency foundation for future long-running mutation endpoints.

## Non-Goals

- No login, registration, refresh tokens, or session tables.
- No repository registration, cloning, parsing, or retrieval logic.
- No domain entities beyond the minimal system metadata table.
- No frontend changes in this phase.

## Deliverables

- Async database manager, repository base classes, and model mixins.
- Alembic environment and initial migration.
- Redis manager and idempotency service.
- Celery app factory and health tasks.
- API error handling, pagination schemas, and middleware updates.
- Backend foundation documentation and failure runbook.
- Updated `.env.example` and README guidance.

## Acceptance Checks

- `alembic upgrade head` works on an empty database.
- `alembic downgrade base` or the phase revision downgrade works.
- `GET /health/ready` reports PostgreSQL, Redis, Qdrant, and Ollama statuses.
- Backend tests, linting, and type checking pass.
- The API and worker use the same validated settings.
- No domain authentication is implemented yet.
