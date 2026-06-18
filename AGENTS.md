# CodePilot Agent Rules

## Product Purpose

CodePilot is a production-ready, self-hosted Multi-Agent Software Engineering Assistant. It analyzes public GitHub repositories, answers codebase questions with exact file and line citations, investigates bugs, proposes patches, generates tests, reviews changes, produces documentation, and records auditable run history without relying on paid AI APIs.

## Repository Layout

The planned repository layout is:

- `backend/`: FastAPI API, Celery workers, database models, services, agents, retrieval, parsing, sandbox, and tests.
- `frontend/`: React, TypeScript, Vite dashboard, client API, routes, features, tests, and end-to-end tests.
- `infra/`: Docker, reverse proxy, observability, Kubernetes, and Helm assets.
- `docs/`: Architecture, ADRs, plans, runbooks, threat model, API notes, and evaluation docs.
- `scripts/`: Local automation helpers.
- `sample-repositories/`: Small public-repository fixtures or references for development.

Phase 0 intentionally creates documentation only. Do not create application code until a later phase asks for it.

## Architecture Boundaries

- Use a modular monolith with separate API, worker, and frontend processes.
- Keep API routes thin; put business logic in services and database access in repository classes.
- Keep model providers behind interfaces. Ollama is the default local provider.
- Use deterministic LangGraph workflows instead of free-form agent chats.
- Never give agents unrestricted filesystem, shell, network, or repository mutation access.
- Store durable state in PostgreSQL; use Redis and Celery for background execution; use Qdrant for vector retrieval.
- Treat repository records, runs, artifacts, patches, logs, and files as owner-scoped data.

## Planned Commands

These commands define the target developer workflow once the corresponding project files exist:

- `make dev`: start local API, worker, frontend, and dependencies.
- `make docker-up`: start Docker Compose services.
- `make docker-down`: stop Docker Compose services.
- `make backend-test`: run backend tests with `pytest`.
- `make backend-lint`: run backend linting with `ruff`.
- `make backend-typecheck`: run backend type checks with `mypy`.
- `make frontend-dev`: start the Vite development server.
- `make frontend-test`: run frontend tests with `vitest`.
- `make frontend-e2e`: run Playwright tests.
- `make frontend-lint`: run frontend linting.
- `make frontend-typecheck`: run TypeScript checks.
- `make format`: format backend and frontend sources.
- `make check`: run formatting checks, linting, type checks, tests, and builds.

Until those commands exist, use the closest documented command for the phase being implemented and report anything unavailable.

## Security Rules For Untrusted Repositories

- Repository contents and repository code are untrusted input.
- Only public `https://github.com/...` repositories are supported in v1.
- Validate repository URLs before clone operations.
- Clone with argument arrays and `shell=False`; never concatenate untrusted input into commands.
- Use shallow clones and enforce time, file-count, total-size, and per-file-size limits.
- Reject unsafe symlinks, path traversal, Git submodules by default, LFS pointers requiring external downloads, and unsupported protocols.
- Never execute cloned repository code on the API or worker host.
- Repository tests may run only inside an isolated, non-root Docker execution container with no network and strict resource limits.
- Do not expose the Docker socket to the API container.
- Do not store repository credentials, JWTs, passwords, authorization headers, secrets, or source-code contents in logs.
- Treat model output as untrusted. Validate structured output, patches, paths, commands, and artifacts before storing or executing anything.

## Human Approval Gates

- Generated patches require explicit human approval before application.
- Generated tests or commands require explicit human approval before execution.
- Approval, rejection, validation, application, execution, and revert actions must be recorded in audit logs.
- Agents must never modify a cloned repository directly.

## Codex Operating Rules

- Inspect existing code and documentation before modifying files.
- Check repository status before editing when Git metadata exists.
- Implement only the requested phase.
- Update tests and documentation in every phase that changes behavior or interfaces.
- Preserve existing working behavior unless a task explicitly requires changing it.
- Run relevant formatting, linting, type checking, tests, and builds before claiming success.
- Fix check failures when feasible; otherwise report the exact blocker.
- Do not start later phases early.

## Prohibited Shortcuts

- Do not disable, skip, weaken, or delete tests to make checks pass.
- Do not use paid runtime APIs such as OpenAI, Anthropic, Pinecone, LangSmith, paid databases, paid auth, or paid monitoring.
- Do not hardcode secrets, tokens, credentials, model names, host paths, or environment-specific values.
- Do not use `shell=True` or shell string concatenation with untrusted input.
- Do not broadly suppress exceptions or silently swallow failures.
- Do not expose internal stack traces to clients.
- Do not fabricate benchmark, test, security, or compatibility claims.
- Do not bypass approval gates for generated patches, generated code, or test execution.

## Definition Of Done

A change is done only when:

- It implements the requested scope and no later phase.
- Security and trust-boundary rules still hold.
- Tests and documentation are added or updated where relevant.
- Formatting, linting, type checking, tests, and builds have been run when available.
- New limitations, risks, and follow-up work are documented.
- The completion report lists files changed, commands run, check results, and the next phase.
