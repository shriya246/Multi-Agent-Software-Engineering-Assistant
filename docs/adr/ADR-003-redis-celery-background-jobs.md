# ADR-003: Redis And Celery For Background Jobs

## Status

Accepted

## Context

Repository ingestion, parsing, indexing, model calls, patch validation, and sandboxed test execution are long-running tasks that should not block HTTP requests.

## Decision

Use Celery for background jobs with Redis as both broker and result backend.

## Consequences

- The API can return durable run identifiers quickly.
- Workers can scale independently from API processes.
- Redis is treated as transient infrastructure, not durable truth.
- Jobs must be idempotent where possible and must persist progress to PostgreSQL.
