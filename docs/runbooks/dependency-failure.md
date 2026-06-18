# Dependency Failure Runbook

## Purpose

This runbook covers the most common Phase 2 dependency failures for local development and the Compose stack.

## First Checks

1. Call `GET /health/ready`.
2. Inspect the `postgres`, `redis`, `qdrant`, and `ollama` checks.
3. Review API and worker logs for connection, timeout, or authentication errors.
4. Confirm the Compose services are running and healthy.

## PostgreSQL Failure

Symptoms:

- `postgres` is degraded in readiness.
- Migrations fail.
- The API cannot persist sessions or metadata.

Checks:

- Confirm the `postgres` container is healthy.
- Confirm `CODEPILOT_DATABASE_URL` points at the Compose service or the expected host.
- Confirm the database user, password, and database name match the Compose defaults.

Remediation:

- Restart the database container.
- Re-run `make migrate` after the service reports healthy.
- If the database volume is corrupted in development, recreate the volume only if you are sure no data needs to be preserved.

## Redis Failure

Symptoms:

- `redis` is degraded in readiness.
- Celery jobs queue but never execute.
- Idempotency reservations fail.

Checks:

- Confirm the `redis` container is healthy.
- Confirm the Redis URL uses the private Compose network service name.
- Check for port conflicts on `6379`.

Remediation:

- Restart the Redis container.
- Restart the worker after Redis is healthy.
- Re-run a no-op worker task if you need to confirm task delivery.

## Qdrant Failure

Symptoms:

- `qdrant` is degraded in readiness.
- Retrieval or semantic indexing features fail later in the project.

Checks:

- Confirm the Qdrant container is healthy.
- Confirm the base URL points at the private Compose service.

Remediation:

- Restart the Qdrant container.
- Check disk space on the mounted volume.

## Ollama Failure

Symptoms:

- `ollama` is degraded in readiness.
- The service starts, but model availability is reported as missing.

Checks:

- Confirm the Ollama container is healthy.
- Confirm the base URL is reachable from the API and worker containers.
- Confirm the expected chat model is installed if you need model-backed features.

Remediation:

- Start or restart Ollama.
- Pull the expected model only when you actually need model-backed features.
- Remember that missing models should not crash the API skeleton.

## When To Escalate

- If storage dependencies fail repeatedly after service restarts.
- If the same container reports health failures after a clean volume reset.
- If readiness shows leaked credentials or unexpected internal topology.
- If database migrations succeed on one machine but fail on another with the same settings.
