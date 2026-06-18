# Backend Foundation

## Scope

Phase 2 establishes the backend runtime foundation for CodePilot. It does not add domain authentication or repository business tables yet. Instead, it creates the platform services the later phases will build on: async PostgreSQL access, Alembic migrations, Redis, Celery, dependency health checks, API conventions, and idempotency support.

## Runtime Building Blocks

- FastAPI provides the HTTP entrypoint and dependency injection.
- SQLAlchemy async sessions provide application request access to PostgreSQL.
- Alembic manages schema migrations with the same validated settings used by the API and worker.
- Redis provides transient queue, result, and idempotency state.
- Celery runs background jobs and scheduled no-op maintenance tasks.
- HTTP health probes check PostgreSQL, Redis, Qdrant, and Ollama with short timeouts.

## Database Pattern

- `app.db.base.Base` defines the SQL naming convention used for all future tables.
- `app.models.base` provides UUID primary keys plus `created_at` and `updated_at` timestamps.
- `app.services.database.DatabaseManager` owns the async engine, session factory, health check, and transaction helper.
- `app.repositories.*` classes stay as the only place that talks to SQLAlchemy sessions directly.
- The initial migration creates a minimal `system_metadata` table so Alembic can upgrade and downgrade an empty database without needing domain entities.

## Redis Pattern

- `app.services.redis.RedisManager` wraps the Redis client and namespace rules.
- JSON serialization is explicit and uses Python `json`, not pickle.
- Keys are prefixed with the environment and application name.
- Idempotency reservations live in Redis and store only request fingerprints and lightweight metadata.

## Celery Pattern

- `app.workers.celery_app.build_celery_app()` creates the configured Celery instance from validated settings.
- Task serialization is JSON-only.
- Task acknowledgements, retries, and worker prefetch settings are tuned for retryable background work.
- `app.workers.tasks.ping` acts as a health task.
- `app.workers.tasks.cleanup_stale_artifacts` is a safe placeholder for future scheduled maintenance.

## API Conventions

- `GET /health/live` reports process liveness.
- `GET /health/ready` reports PostgreSQL, Redis, Qdrant, and Ollama status.
- `GET /api/v1/version` reports version metadata.
- Errors return the shared envelope and never expose stack traces.
- Request sizes are bounded before route processing.
- Trusted hosts are enabled in production.

## Dependency Injection

- `app.state.settings` stores the validated settings object.
- `app.state.container` stores the shared database and Redis managers.
- API dependencies in `app.api.v1.dependencies` expose the container, session-oriented services, and pagination helpers.
- This keeps routes thin and gives future handlers a single place to request shared infrastructure.

## Operational Checks

- `make migrate` runs Alembic against the Compose PostgreSQL service.
- `make backend-test` runs the isolated backend test suite.
- `make backend-lint` and `make backend-typecheck` enforce style and typing.
- `make check` runs the full backend and frontend local quality pass.

## Phase 2 Verification Notes

- Alembic upgrade and downgrade are covered by integration tests using a temporary database.
- Database rollback, Redis health, idempotency, Celery config, request-size rejection, and readiness behavior are covered by unit tests.
- The readiness endpoint is intentionally conservative: storage failures degrade readiness, while missing Ollama models are reported separately from the service availability check.
