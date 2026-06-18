# ADR-005: Ollama Provider Abstraction

## Status

Accepted

## Context

The product must run locally without paid AI APIs, while leaving room for future model providers.

## Decision

Use Ollama as the default chat and embedding provider behind explicit provider interfaces. Model names are configured through environment variables and documented sample defaults, not hardcoded.

## Consequences

- The initial system can run without OpenAI, Anthropic, or other paid APIs.
- Provider contracts make future additions possible.
- Model output must be validated because local models can return malformed or unsafe content.
- Tests should use fakes or fixtures rather than requiring a local model for every check.
