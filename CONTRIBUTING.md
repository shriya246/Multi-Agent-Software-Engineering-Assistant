# Contributing

## Branches

- Use short, descriptive branch names such as `phase-02-auth-foundation` or `fix-patch-path-validation`.
- Keep each branch focused on one phase or one narrowly scoped fix.
- Do not mix unrelated refactors with feature work.

## Commits

- Use clear imperative commit messages, such as `Add repository ingestion threat model`.
- Keep commits reviewable.
- Do not commit secrets, local environment files, generated credentials, model downloads, database volumes, or cloned repositories.

## Development Expectations

- Read [AGENTS.md](AGENTS.md) before making changes.
- Inspect the existing repository and Git status before editing.
- Implement only the requested phase or issue.
- Update tests and documentation for each behavior or interface change.
- Keep API routes thin, business logic in services, and database access behind repository classes.
- Treat repository code, model output, patches, logs, and test output as untrusted data.

## Testing And Checks

Run the relevant checks before opening a review. Planned commands include:

- `make format`
- `make backend-lint`
- `make backend-typecheck`
- `make backend-test`
- `make frontend-lint`
- `make frontend-typecheck`
- `make frontend-test`
- `make frontend-e2e`
- `make check`

If a command is not available yet, state that in the review notes and run the closest phase-appropriate check.

## Review Expectations

Reviews should verify:

- The change matches the requested phase.
- Security boundaries remain intact.
- Human approval gates are preserved.
- Repository code never runs on the host.
- Tests cover the meaningful risk.
- Documentation and examples match the implementation.
- Errors are explicit and do not leak internal traces or secrets.
