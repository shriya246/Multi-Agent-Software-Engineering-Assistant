# ADR-008: Public GitHub Repositories Only In V1

## Status

Accepted

## Context

Supporting private repositories, credentials, multiple Git hosts, submodules, and write-back flows would expand the threat model and implementation complexity.

## Decision

Support only public repositories hosted at normalized `https://github.com/...` URLs in v1.

## Consequences

- No repository credentials are needed in the initial release.
- URL validation, SSRF mitigation, and clone policy are simpler.
- Users cannot ingest private repositories yet.
- Future support for private repositories must update the threat model, auth model, storage rules, and audit requirements.
