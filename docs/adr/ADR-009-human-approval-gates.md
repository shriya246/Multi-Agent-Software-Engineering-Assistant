# ADR-009: Human Approval Gates

## Status

Accepted

## Context

Model output, generated patches, generated tests, and repository code are untrusted. Automatically applying or executing generated changes can damage repositories or run malicious code.

## Decision

Require explicit human approval before applying generated patches or executing generated code and tests. Record approval, rejection, validation, execution, application, and revert actions in audit logs.

## Consequences

- Users stay in control of risky actions.
- The API must model approval state explicitly.
- The frontend must make review, approval, rejection, validation, and execution status clear.
- Approval reduces risk but does not replace validation and sandboxing.
