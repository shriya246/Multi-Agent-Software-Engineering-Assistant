# ADR-004: Qdrant For Vector Search

## Status

Accepted

## Context

CodePilot needs semantic code retrieval in addition to lexical search. The vector store must be locally runnable and open source.

## Decision

Use Qdrant for vector indexes and store ownership, repository, revision, file, and chunk identifiers as payload metadata.

## Consequences

- Semantic retrieval can be developed locally without a paid vector database.
- PostgreSQL remains the authorization source of truth.
- Retrieval must always filter by owner and repository scope.
- Index rebuild and deletion workflows are required when repositories change or are removed.
