# CodePilot

CodePilot is a self-hosted Multi-Agent Software Engineering Assistant for analyzing software repositories, answering codebase questions, diagnosing bugs, proposing patches, generating tests, reviewing changes, and producing documentation.

The project is designed as an engineering-quality portfolio system with local, open-source runtime dependencies by default. Phases 1-3 provide the local development skeleton, backend foundation, owner-scoped domain schema, and secure local authentication with rotating refresh sessions.

## Prerequisites

- Python 3.11.x
- Node.js 25.x with `npm`
- Docker Desktop or Docker Engine with Compose support
- Git

Optional but recommended:

- `uv` for backend dependency management
- `make` for cross-platform convenience targets

## Windows And WSL Guidance

- On Windows PowerShell, use the provided `scripts/*.ps1` helpers and `npm.cmd` where needed.
- If PowerShell execution policy blocks scripts, run them from an elevated shell or use WSL.
- WSL2 is the smoothest path for Docker Compose, local package installs, and shell-based checks.
- The repo includes `npm.cmd`-friendly and `python -m uv`-friendly commands so you do not need a global `uv` binary on PATH.

## Local Installation

1. Copy `.env.example` to `.env` and adjust any local overrides.
2. Install backend dependencies with `python -m uv sync --project backend --group dev`.
3. Install frontend dependencies with `cd frontend && npm install`.
4. Start the development stack with `docker compose up --build`.
5. Run `make migrate` after PostgreSQL is healthy to create the minimal system metadata table.

## Docker Installation

Docker Compose is the default local orchestration path. The stack includes:

- `api`
- `worker`
- `frontend`
- `postgres`
- `redis`
- `qdrant`
- `ollama`

Development Compose publishes service ports only on `127.0.0.1`. The base Compose file does not publish database, Redis, Qdrant, or Ollama ports publicly.

## Starting Services

- `make bootstrap`
- `make dev`
- `make logs`
- `make down`

Windows PowerShell equivalents:

- `./scripts/bootstrap.ps1`
- `docker compose up --build`
- `./scripts/check.ps1`
- `docker compose logs -f --tail=200`
- `docker compose down`

## Running Checks

- `make backend-test`
- `make backend-lint`
- `make backend-typecheck`
- `make frontend-test`
- `make frontend-lint`
- `make frontend-typecheck`
- `make check`

The repo also includes `scripts/check.sh` and `scripts/check.ps1` for a single local verification pass.

## Environment Configuration

Key environment variables live in `.env.example`:

- `CODEPILOT_ENVIRONMENT`
- `CODEPILOT_SECRET_KEY`
- `CODEPILOT_TRUSTED_HOSTS`
- `CODEPILOT_MAX_REQUEST_SIZE_BYTES`
- `CODEPILOT_DATABASE_URL`
- `CODEPILOT_DATABASE_POOL_SIZE`
- `CODEPILOT_DATABASE_MAX_OVERFLOW`
- `CODEPILOT_DATABASE_POOL_TIMEOUT_SECONDS`
- `CODEPILOT_DATABASE_CONNECT_TIMEOUT_SECONDS`
- `CODEPILOT_DATABASE_STATEMENT_TIMEOUT_MS`
- `CODEPILOT_REDIS_URL`
- `CODEPILOT_REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS`
- `CODEPILOT_REDIS_SOCKET_TIMEOUT_SECONDS`
- `CODEPILOT_REDIS_HEALTH_TIMEOUT_SECONDS`
- `CODEPILOT_QDRANT_URL`
- `CODEPILOT_QDRANT_HEALTH_TIMEOUT_SECONDS`
- `CODEPILOT_OLLAMA_BASE_URL`
- `CODEPILOT_OLLAMA_HEALTH_TIMEOUT_SECONDS`
- `CODEPILOT_OLLAMA_CHAT_MODEL`
- `CODEPILOT_OLLAMA_EMBEDDING_MODEL`
- `CODEPILOT_CELERY_TASK_TIME_LIMIT_SECONDS`
- `CODEPILOT_CELERY_TASK_SOFT_TIME_LIMIT_SECONDS`
- `CODEPILOT_CELERY_RESULT_EXPIRES_SECONDS`
- `CODEPILOT_CELERY_WORKER_PREFETCH_MULTIPLIER`
- `CODEPILOT_IDEMPOTENCY_TTL_SECONDS`
- `VITE_API_BASE_URL`

The API starts without requiring an Ollama model to be installed. Readiness reports model availability separately rather than crashing the service.

Phase 2 backend capabilities also include:

- Async SQLAlchemy sessions and transaction helpers
- Alembic upgrade and downgrade support
- Redis JSON helpers and namespaced idempotency reservations
- Celery JSON-only tasks and a no-op cleanup schedule
- Standardized API error envelopes and pagination schemas
- Request-size limits and trusted-host checks

## Service URLs

Development defaults:

- API: `http://127.0.0.1:8000`
- Frontend: `http://127.0.0.1:5173`
- PostgreSQL: `127.0.0.1:5432`
- Redis: `127.0.0.1:6379`
- Qdrant: `http://127.0.0.1:6333`
- Ollama: `http://127.0.0.1:11434`

## Troubleshooting

- If `npm` fails in PowerShell, use `npm.cmd` or run the command inside WSL.
- If Docker health checks stay pending, confirm the containers have enough CPU and memory and that no old volumes are blocking startup.
- If the API reports readiness as degraded, check whether PostgreSQL, Redis, Qdrant, and Ollama are running and whether the environment variables point at the Compose service names.
- If `uv` is missing, run `python -m pip install --user uv`.
- If port `8000` or `5173` is already in use, stop the conflicting process or adjust the Compose override ports.

## Documentation

- [Agent rules](AGENTS.md)
- [System overview](docs/architecture/system-overview.md)
- [API outline](docs/architecture/api-outline.md)
- [Threat model](docs/threat-model/threat-model.md)
- [Roadmap](docs/plans/roadmap.md)
- [Phase 0 plan](docs/plans/phase-00.md)
- [Phase 1 plan](docs/plans/phase-01.md)
- [Phase 2 plan](docs/plans/phase-02.md)
- [Phase 3 plan](docs/plans/phase-03.md)
- [Authentication and authorization](docs/architecture/authentication.md)

## License

CodePilot is licensed under the MIT License. See [LICENSE](LICENSE).
