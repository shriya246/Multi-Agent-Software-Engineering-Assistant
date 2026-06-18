# ADR-002: PostgreSQL As Source Of Truth

## Status

Accepted

## Context

CodePilot needs durable owner-scoped records for users, repositories, revisions, files, symbols, runs, events, artifacts, patches, test executions, refresh tokens, and audit logs.

## Decision

Use PostgreSQL as the durable source of truth, accessed through async SQLAlchemy and migrated with Alembic.

## Consequences

- Relational constraints and indexes can protect ownership and workflow invariants.
- PostgreSQL supports transactional updates for runs, approvals, and audit records.
- Qdrant and Redis remain secondary stores and must be rebuildable or transient.
- Schema changes require disciplined migrations and tests.
