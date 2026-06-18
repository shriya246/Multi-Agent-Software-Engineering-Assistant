# ADR-007: Docker Sandbox Execution

## Status

Accepted

## Context

Generated tests and repository commands are untrusted. The API and worker host must never directly execute cloned repository code.

## Decision

Run approved test execution inside an isolated, non-root Docker container with no network access, strict resource limits, no Docker socket, and bounded logs.

## Consequences

- Local users can execute tests with a practical isolation boundary.
- The system must clearly document that Docker is not a hardened microVM sandbox.
- Sandbox setup requires careful mount, user, network, timeout, and cleanup controls.
- All execution requires explicit human approval and audit records.
