# Phase 0 Plan

## Scope

Phase 0 establishes the project constitution, architecture plan, threat model, operating rules, and roadmap for CodePilot.

## Goals

- Document the product purpose and engineering constraints.
- Define architecture boundaries before implementation begins.
- Define the planned API surface for authentication, repositories, agent runs, patches, execution, and artifacts.
- Treat repository source code as untrusted throughout the design.
- Record the first set of architecture decisions.
- Prepare future Codex tasks to inspect the repository, update docs and tests, and stop at the requested phase.

## Non-Goals

- No backend application code.
- No frontend application code.
- No Docker runtime configuration.
- No database schema.
- No package manifests or dependency lock files.
- No model, parser, queue, or sandbox integration.

## Deliverables

- Root `AGENTS.md`.
- Root `README.md`, `SECURITY.md`, `CONTRIBUTING.md`, and `LICENSE`.
- `docs/architecture/system-overview.md`.
- `docs/architecture/api-outline.md`.
- `docs/threat-model/threat-model.md`.
- ADRs 001 through 010.
- `docs/plans/roadmap.md`.
- Workspace-local sample `.codex/config.toml`.

## Acceptance Checks

- Confirm no application code exists.
- Confirm architecture documents agree on component responsibilities and approval gates.
- Confirm source code is explicitly treated as untrusted.
- Confirm API outline includes run history, artifacts, patch approval, validation, execution, apply, and revert endpoints.
- Confirm Mermaid diagrams use standard `flowchart` and `sequenceDiagram` syntax.
- Run available Markdown formatting or link checks. If no formatter or link checker exists, run a lightweight file and content inspection.

## Phase 0 Result

Phase 0 is complete when all documentation deliverables exist and no Phase 1 application scaffold has been created.
