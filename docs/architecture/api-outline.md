# API Outline

This document defines the planned HTTP surface for `v1`. The API is owner-scoped: users may access only their own repositories, runs, patches, artifacts, and audit-visible records.

All endpoints return standard error responses, use correlation IDs, and avoid leaking internal stack traces. Long-running work returns durable run, job, or execution identifiers and emits events.

## Authentication

### POST /api/v1/auth/register

Creates a user account.

Planned request fields: email, password, display name.

Planned response: user profile, access token, refresh token metadata.

### POST /api/v1/auth/login

Authenticates a user.

Planned request fields: email, password.

Planned response: user profile, access token, refresh token metadata.

### POST /api/v1/auth/refresh

Rotates a refresh token and returns a new access token.

Planned request fields: refresh token.

Planned response: access token, refresh token metadata.

### POST /api/v1/auth/logout

Revokes the current refresh token or session.

Planned request fields: refresh token or current session identifier.

Planned response: logout status.

### GET /api/v1/auth/me

Returns the authenticated user profile.

## Repositories

### POST /api/v1/repositories

Registers a public GitHub repository after validating that the URL uses HTTPS and belongs to `github.com`.

Planned request fields: repository URL, optional display name, idempotency key.

Planned response: repository record and ingestion run identifier.

### GET /api/v1/repositories

Lists repositories owned by the authenticated user.

Planned query fields: pagination, status, sort.

### GET /api/v1/repositories/{repository_id}

Returns a repository owned by the authenticated user.

### DELETE /api/v1/repositories/{repository_id}

Deletes or archives a repository record and schedules cleanup of associated local clone data and indexes.

### POST /api/v1/repositories/{repository_id}/index

Starts or restarts indexing for the repository.

Planned response: indexing run identifier.

### GET /api/v1/repositories/{repository_id}/files

Lists indexed files for a repository.

Planned query fields: revision, path prefix, language, pagination.

### GET /api/v1/repositories/{repository_id}/symbols

Lists indexed symbols for a repository.

Planned query fields: revision, symbol kind, name query, file path, pagination.

## Agent Runs

### POST /api/v1/repositories/{repository_id}/questions

Starts a codebase question-answering run.

Planned request fields: question, optional revision, retrieval limits.

Planned response: run identifier.

### POST /api/v1/repositories/{repository_id}/bug-fixes

Starts a bug investigation run with optional patch generation.

Planned request fields: bug description, failing behavior, optional files, optional logs, optional revision.

Planned response: run identifier.

### POST /api/v1/repositories/{repository_id}/test-generations

Starts a test generation run.

Planned request fields: target behavior, optional files, optional framework hints, optional revision.

Planned response: run identifier.

### POST /api/v1/repositories/{repository_id}/reviews

Starts an automated code review run for a diff, patch, or selected repository scope.

Planned request fields: diff or patch ID, review focus, optional revision.

Planned response: run identifier.

### POST /api/v1/repositories/{repository_id}/documentation

Starts a documentation generation run.

Planned request fields: topic, output type, optional files, optional revision.

Planned response: run identifier.

### GET /api/v1/runs/{run_id}

Returns run status, request summary, node states, timing, model metadata, and result summary.

### GET /api/v1/runs/{run_id}/events

Returns run events for polling or streaming.

Planned query fields: cursor, limit, event type.

### POST /api/v1/runs/{run_id}/cancel

Requests cancellation of a running job. Workers stop at safe checkpoints.

## Patches And Execution

### GET /api/v1/patches/{patch_id}

Returns a generated patch, validation status, approval status, related run, and artifacts.

### POST /api/v1/patches/{patch_id}/approve

Records human approval for a patch. Approval does not apply or execute the patch by itself.

Planned request fields: approval note.

### POST /api/v1/patches/{patch_id}/reject

Records human rejection for a patch.

Planned request fields: rejection reason.

### POST /api/v1/patches/{patch_id}/validate

Validates a patch without applying it to the durable repository record.

Validation includes unified diff structure, path traversal checks, target file existence, size limits, and conflict checks.

### POST /api/v1/patches/{patch_id}/execute-tests

Runs approved tests for an approved patch inside the isolated Docker sandbox.

This endpoint requires explicit human approval and records a `TestExecution` and `AuditLog` entry.

### POST /api/v1/patches/{patch_id}/apply

Applies an approved and validated patch to a controlled workspace or planned branch target.

This endpoint requires explicit human approval and records an audit event.

### POST /api/v1/patches/{patch_id}/revert

Reverts a previously applied patch where supported.

This endpoint requires authorization and records an audit event.

## Artifacts

### GET /api/v1/runs/{run_id}/artifacts

Lists artifacts created by a run.

Artifacts may include answers, evidence bundles, generated docs, generated tests, review reports, validation reports, and bounded sandbox logs.

### GET /api/v1/artifacts/{artifact_id}

Returns an artifact owned by the authenticated user.

Large artifacts should use pagination, streaming, or download metadata as appropriate.

## Run History And Audit

Run history is exposed through run and artifact endpoints. Audit records are planned as an internal and administrative surface first, with future user-visible endpoints considered after authorization requirements are defined.

Every human approval, rejection, patch validation, patch application, sandbox execution, cancellation, authentication event, and repository deletion must create an audit record.
