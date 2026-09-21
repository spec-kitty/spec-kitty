# Tracer: Design Decisions

Load-bearing decisions and their rationale. Seeded at planning; append as decisions are made.

## D-1 — Canonical helper home: the `auth` package (server_target.py), not saas_client
`saas_client` is a *client of upstream* (API shape authored upstream) but freely imports host-side auth
already; the issuer/target rule is auth-subsystem semantics. Home it where `resolve_server_target` and the
canonical `_normalize_url` already live so the security equality check reuses ONE normalizer. Both existing
guards (`saas_client._guard_session_issuer`, `_auth_saas_target.format_saas_mismatch_warning`) consume it.

## D-2 — Refusal is a new typed error `IssuerTargetMismatchError(AuthenticationError)`
Not `RefreshTokenExpiredError` (wrong remedy — implies the token died, not the target is wrong). The
refresh-path refusal MUST be a type the `saas_client._usable_access_token` bare-`except` cannot demote to
"use the held token" (add to `_dead_session_errors()` / raise as `SaasAuthError` at that boundary), else the
leak re-opens.

## D-3 — Guard/resolve at the TokenManager boundary for refresh, not deep inside the in-lock flow
Refresh runs inside a machine-wide lock; resolving there risks `ServerTargetSplitBrainError` leaking into an
error contract the in-lock flow does not express. Resolve+guard at the boundary.

## D-4 — Per-flow refusal adapters (the refusal must not be swallowed into a send)
- refresh: raise `IssuerTargetMismatchError` (in `_dead_session_errors()`), guard before the POST.
- revoke: never raises → add `RevokeOutcome.ISSUER_MISMATCH`, guard before the try (so `except` cannot fold it into SERVER_FAILURE).
- rehydrate: best-effort → fail-closed to a specific WARNING + no send (do NOT upgrade to a hard raise).
- ws: wrap into `WebSocketProvisioningError`, guard before the send + before get_access_token.

## D-5 — Legacy `issuer_url = None` routes to the resolved target, no refusal
Otherwise legacy self-hosted sessions keep leaking to the packaged default.

## D-6 — Preserve the display-vs-raise duality when unifying `_auth_saas_target.format_saas_mismatch_warning`
That helper RETURNS a display string for `auth login`; the shared helper is raise-based. Unification must keep
a display adapter so `auth login`'s UX is unchanged.

## (append as decisions land)
