# ADR-001: Modular Monolith

## Status

Accepted

## Context

CodePilot needs a production-quality structure without adding distributed-system complexity before the product boundaries are proven. The system has clear API, worker, and frontend processes, but most backend business logic benefits from shared models, transactions, and deployable coherence.

## Decision

Use a modular monolith for the backend. The API and worker run as separate processes from the same backend codebase, with modules for API routes, services, repositories, agents, retrieval, parsing, sandboxing, security, and observability.

## Consequences

- Development remains understandable for a portfolio-scale system.
- Database transactions and shared domain rules are easier to maintain.
- Modules must enforce boundaries through package structure, tests, and review discipline.
- Future service extraction remains possible after interfaces and bottlenecks are known.
