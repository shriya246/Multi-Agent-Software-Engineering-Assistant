# Roadmap

## Phase 0: Project Constitution, Architecture, And Codex Rules

Create the documentation foundation: agent rules, architecture overview, API outline, threat model, ADRs, roadmap, and project governance docs. Do not implement application code.

## Phase 1: Repository Scaffold And Local Tooling

Create the planned directory structure, backend and frontend package manifests, editor config, Git ignore rules, Makefile, Docker Compose files, pre-commit hooks, and initial CI skeleton.

## Phase 2: Backend Foundation

Implement FastAPI application setup, pydantic-settings configuration, async SQLAlchemy, Alembic, PostgreSQL connectivity, health and readiness endpoints, structured logging, correlation IDs, standard error responses, and authentication foundation.

## Phase 3: Repository Registration And Secure Cloning

Implement public GitHub URL validation, repository ownership, shallow clone jobs, clone limits, submodule and symlink rejection, file discovery, cleanup policies, and ingestion audit records.

## Phase 4: Parsing, Symbols, And Lexical Search

Add Tree-sitter parsing, supported-language detection, repository file persistence, symbol extraction, lexical search, file and symbol APIs, and parser fixtures.

## Phase 5: Semantic Indexing And Retrieval

Implement embedding provider interfaces, Qdrant integration, chunking, vector indexing, hybrid retrieval, retrieval tests, and index rebuild flows.

## Phase 6: Local Model Provider Abstraction

Add Ollama chat and embedding clients behind interfaces, configurable model names, structured output validation, retries, timeouts, prompt versioning, and provider tests.

## Phase 7: Agent Workflow Foundation

Implement deterministic LangGraph workflows, node contracts, run state machine, event persistence, artifact persistence, cancellation checkpoints, and agent observability.

## Phase 8: Codebase Question Answering

Implement question-answering runs with bounded context, lexical and semantic retrieval, code reading, evidence tracking, exact file and line citations, and answer artifacts.

## Phase 9: Bug Investigation And Patch Generation

Implement bug analysis, root-cause reporting, unified diff generation, patch schema validation, path safety checks, conflict detection, patch artifacts, and approval state.

## Phase 10: Test Generation And Sandboxed Execution

Implement generated tests, human approval for execution, Docker sandbox runner, no-network execution, resource limits, bounded logs, test execution records, and sandbox warnings.

## Phase 11: Automated Review And Documentation

Implement code review workflows, documentation generation workflows, structured review findings, documentation artifacts, and evidence-linked reports.

## Phase 12: React Dashboard

Implement authentication screens, repository list and detail views, run history, streamed events, artifact views, patch review, approval actions, Monaco diff display, and core frontend tests.

## Phase 13: Observability And Production Compose

Add Prometheus metrics, OpenTelemetry traces, Grafana dashboards, Jaeger or Tempo, production Compose hardening, private service exposure, runbooks, and backup notes.

## Phase 14: CI, Evaluation, And Release Readiness

Add GitHub Actions checks, frontend end-to-end tests, backend integration tests, sample repositories, evaluation fixtures, release documentation, and final security review.
