# Phase 4 - Secure GitHub Repository Ingestion

Phase 4 adds authenticated ingestion of public GitHub repositories. It validates repository URLs, queues owner-scoped ingestion work, clones through a bounded Git subprocess, scans files as untrusted input, and records safe progress metadata for the UI.

## Implemented Scope

- Public `https://github.com/{owner}/{repository}` URL validation and normalization.
- Optional branch, tag, or commit ref validation as a separate API field.
- Owner-scoped repository, file, run, and run event endpoints.
- Celery tasks for ingestion and repository cleanup.
- Shell-free Git command construction with `GIT_TERMINAL_PROMPT=0` and credential helper disabled.
- Shallow clone behavior with timeout and bounded captured process output.
- Workspace directories generated server-side and removed after ingestion attempts.
- File scanning with POSIX normalized paths, binary/media/secret-like exclusions, `.codepilotignore`, symlink exclusion, SHA-256 hashes, language hints, byte counts, and line counts.
- Repository state transition enforcement for `queued`, `cloning`, `scanning`, `ready_for_indexing`, `indexing`, `ready`, `failed`, `deleting`, and `deleted`.
- Retry-safe duplicate submission behavior for active ingestion jobs.
- Minimal repository list, add form, detail page, progress status, file summary, failure state, sync, and delete UI.

## Security Notes

Repository code is never executed by the API or worker. Clone commands are built as argument arrays and run with `shell=False`. The scanner treats repository paths and contents as untrusted data, does not follow symlinks, enforces configured limits, and never returns local workspace paths or raw Git stderr to clients.

Deletion marks repositories as `deleting` and queues cleanup. Future indexing phases must remove Qdrant vectors during the same cleanup workflow while preserving audit logs according to retention policy.

## Configurable Limits

The following settings are exposed with `CODEPILOT_` environment variables:

- `INGESTION_WORKSPACE_ROOT`
- `INGESTION_CLONE_TIMEOUT_SECONDS`
- `INGESTION_PROCESS_OUTPUT_BYTES`
- `INGESTION_MAX_TOTAL_BYTES`
- `INGESTION_MAX_FILES`
- `INGESTION_MAX_FILE_BYTES`
- `INGESTION_MAX_PATH_LENGTH`
- `INGESTION_MAX_NESTING_DEPTH`
- `INGESTION_MAX_TEXT_LINES`
- `INGESTION_MAX_SYMLINKS`
- `INGESTION_FAILED_WORKSPACE_TTL_SECONDS`

## Deferred

Embeddings, symbol extraction, Qdrant writes, agent workflows, and sandboxed repository test execution are intentionally deferred to later phases.
