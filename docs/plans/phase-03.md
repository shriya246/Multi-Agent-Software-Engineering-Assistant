# Phase 3 Plan

## Scope

Phase 3 adds local authentication, authorization dependencies, owner boundaries, the core domain schema, and the minimum browser authentication UI. It does not clone or index repositories and does not add repository management UI.

## Delivered

- Argon2id password hashing and generic login failures.
- Short-lived signed access tokens plus opaque, rotating refresh tokens stored only as SHA-256 hashes.
- Refresh-family revocation on replay, per-session logout, and logout of all sessions.
- HTTP-only SameSite refresh cookies and double-submit CSRF checks for cookie-authenticated mutations.
- Redis-backed registration, login, password-verification, refresh, and authenticated-API rate limits.
- Current/active-user and role dependencies plus owner-scoped repository and run repositories.
- Reversible schema migration for users, repositories, revisions, files, symbols, runs, events, artifacts, patches, executions, and audits.
- Register/login pages, session bootstrap, protected routes, current-user menu, and logout with access tokens held only in memory.

## Non-Goals

- Social login, password reset, and email verification delivery.
- Repository registration, cloning, indexing, or repository UI.
- Agent workflows, patch application, or test execution.
- Administrator endpoints; role enforcement is provided for later phases.

## Verification

Backend tests cover password hashing, token expiry and rotation, refresh replay, logout, disabled users, rate limiting and outages, CSRF, owner scoping, audit records, constraints, OpenAPI paths, and migration upgrade/downgrade. Frontend tests cover public rendering and protected-route behavior.
