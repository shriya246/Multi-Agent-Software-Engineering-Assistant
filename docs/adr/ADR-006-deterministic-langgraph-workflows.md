# ADR-006: Deterministic LangGraph Workflows

## Status

Accepted

## Context

CodePilot needs auditable agent behavior, typed outputs, retry limits, and clear node responsibilities. Free-form multi-agent chat is harder to verify and debug.

## Decision

Use deterministic LangGraph workflows with named nodes, bounded context, typed structured output, evidence requirements, timeouts, retry limits, and run event recording.

## Consequences

- Agent runs are easier to inspect, test, and resume.
- Not every request needs every node.
- Workflow definitions must stay explicit and versioned.
- Prompt injection risk is reduced but not eliminated.
