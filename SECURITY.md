# Security Policy

## Reporting Vulnerabilities

This project is in the planning phase. Until a dedicated private reporting channel exists, do not publish suspected vulnerabilities in public issues. Contact the project maintainer directly through the repository owner's preferred private channel.

When reporting a vulnerability, include:

- Affected component or document.
- Reproduction steps.
- Expected and actual impact.
- Any logs or screenshots with secrets removed.
- Suggested mitigation, if known.

## Security Boundaries

CodePilot is designed for local or trusted single-tenant self-hosted use in its initial production-ready release. Docker sandboxing reduces risk for approved test execution, but it is not equivalent to a hardened microVM sandbox for hostile public multi-tenant execution.

## Untrusted Repository Rule

Repository contents and repository code are untrusted input. The application must not:

- Execute cloned repository code on the API or worker host.
- Treat repository text as trusted instructions.
- Run generated commands or generated tests without explicit human approval.
- Apply generated patches without explicit human approval.
- Clone unsupported protocols or non-GitHub URLs in v1.
- Store secrets, credentials, JWTs, passwords, authorization headers, or source-code contents in logs.

## Supported Repository Scope

The initial release supports public repositories hosted at `https://github.com/...` only. Private repositories, other Git hosts, submodules, Git LFS downloads, and write-back integrations are out of scope until later threat-model updates approve them.

## Sandbox Boundary

Approved test execution must run inside an isolated, non-root Docker container with:

- No network access.
- Read-only repository input where practical.
- CPU, memory, process, and timeout limits.
- No Docker socket exposure.
- No privileged container mode.
- Captured logs with secret redaction and size limits.

## Dependency Boundary

Runtime dependencies must be open source and locally runnable by default. Paid model APIs, paid vector databases, paid authentication providers, and paid monitoring services are not accepted runtime dependencies.
