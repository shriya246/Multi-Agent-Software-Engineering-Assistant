# Phase 5 - AST Parsing, Symbol Extraction, And Code Indexing

Phase 5 adds syntax-aware repository parsing, symbol extraction, code chunk indexing, and repository search surfaces. It stores file content for safe post-clone indexing, builds durable index snapshots, and exposes the new indexing workflow through the API and dashboard.

## Implemented Scope

- Syntax-aware Python parsing with heuristic parsers for JavaScript, TypeScript, Java, C#, C++, and Go.
- Safe fallback parsing for unsupported or broken files so indexing continues with partial data.
- Repository file content persistence for indexing after the workspace is cleaned up.
- Durable code symbol and code chunk storage tied to repository revisions and snapshots.
- Incremental embedding reuse across revisions for unchanged chunks.
- Hybrid repository search with lexical and dense ranking over indexed chunks.
- Repository index status, symbol listing, and code search endpoints.
- Dashboard controls for triggering indexing, reviewing index statistics, browsing symbols, and searching indexed code.
- Parser fixtures and backend/frontend tests for supported languages and incremental indexing behavior.

## Security Notes

- Repository contents remain untrusted input and are parsed without executing cloned code.
- The dashboard only exposes owner-scoped repository data.
- Search and indexing endpoints use the same owner-scoped authorization rules as the rest of the API.

## Configurable Limits

- `CODEPILOT_INDEXING_CHUNK_MAX_CHARS`
- `CODEPILOT_INDEXING_CHUNK_MAX_LINES`
- `CODEPILOT_INDEXING_CHUNK_OVERLAP_LINES`
- `CODEPILOT_INDEXING_EMBEDDING_BATCH_SIZE`
- `CODEPILOT_INDEXING_EMBEDDING_TIMEOUT_SECONDS`
- `CODEPILOT_INDEXING_EMBEDDING_DIMENSIONS`
- `CODEPILOT_INDEXING_TOP_K`
- `CODEPILOT_INDEXING_SEARCH_RATE_LIMIT`

## Deferred

Future phases may refine the local embedding provider integration, expand retrieval strategies, and add the remaining agent workflows, sandboxed execution, and review automation.
