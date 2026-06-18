# Phase 1 Plan

## Scope

Phase 1 creates the reproducible monorepo bootstrap for CodePilot: backend skeleton, frontend skeleton, Docker Compose, developer scripts, quality commands, and lockfiles.

## Goals

- Establish supported Python and Node toolchains.
- Add a minimal FastAPI application factory with health and version endpoints.
- Add typed settings, structured logging, correlation IDs, and error envelopes.
- Add a minimal React, TypeScript, Vite shell with routing and client foundation.
- Add Dockerfiles, Compose files, and local development scripts.
- Commit backend and frontend lockfiles for reproducible builds.

## Non-Goals

- No authentication flows.
- No database tables or domain models.
- No repository ingestion or cloning logic.
- No parsing, retrieval, model orchestration, or sandbox execution.
- No CI workflow.

## Deliverables

- Backend package scaffold and tests.
- Frontend package scaffold and tests.
- `compose.yaml` and `compose.override.yaml`.
- Root `Makefile`, scripts, `.env.example`, `.editorconfig`, `.gitignore`, and pre-commit config.
- Backend `uv.lock` and frontend `package-lock.json`.
- README updates for local development and troubleshooting.

## Acceptance Checks

- `docker compose config` succeeds.
- Backend tests pass.
- Backend lint and type checks pass.
- Frontend tests, lint, and type checks pass.
- No committed secrets or production credentials.
- No later-phase application features have been added.
