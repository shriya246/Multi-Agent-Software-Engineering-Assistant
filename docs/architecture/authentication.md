# Authentication And Authorization

## Session Design

Passwords use Argon2id through `argon2-cffi` and are never retained after verification. Access tokens are signed JWTs with a 15-minute default lifetime and are held only in frontend memory. The signing key comes from configuration and production startup rejects the development key or a key shorter than 32 characters.

Refresh tokens are random opaque values. Only their SHA-256 hashes are stored. Every refresh revokes the presented record, creates a replacement in the same family, and links the two records. Presenting a revoked token is treated as replay and revokes every active token in that family.

The browser receives the refresh token in an HTTP-only, SameSite=Lax cookie scoped to `/api/v1/auth`. A separate readable SameSite cookie is submitted in `X-CSRF-Token` and compared with constant-time equality for refresh, logout, and logout-all. Production deployments must set `CODEPILOT_COOKIE_SECURE=true` behind HTTPS.

## Authorization Boundaries

The current-user dependency validates an access token, loads the durable user, rejects disabled accounts, and applies the authenticated API limit. Role dependencies are deny-by-default. Repository and run repository methods require the owner ID in the same query as the resource ID; an absent resource and another user's resource both return `None` so UUID existence is not disclosed.

## Rate-Limit Outage Policy

Authentication limits fail closed by default when Redis is unavailable because uncontrolled credential verification is the higher risk. General authenticated API limiting fails open so an established session can continue using non-authentication functionality during a transient Redis outage. `CODEPILOT_AUTH_RATE_LIMIT_FAIL_CLOSED` and every limit are configurable.

## Audit And Metadata Rules

Authentication success, failure, logout, logout-all, refresh, and replay events are durable audit records. IP addresses and user agents are one-way hashed with application-secret context; tokens, passwords, authorization headers, and source text are forbidden from logs and audit details.

Private run-event metadata is internal-only and must contain a small allowlisted structured payload: identifiers, bounded counts, timings, state names, and sanitized error codes. It must never contain source contents, prompts, credentials, tokens, headers, raw command output, or unsanitized exceptions. Later services that emit run events must validate this contract before persistence.
