---
title: 'ADR: Centralized Auth Transport Boundary'
description: 'Makes one module the sole owner of authenticated HTTP: bearer injection, 401 refresh-and-retry-once, and deduplicated failure reporting behind singleton clients.'
status: Accepted
doc_status: active
kind: ADR
date: '2026-04-26'
---

- `kitty-specs/stability-and-hygiene-hardening-2026-04-01KQ4ARB/research.md` (D9, D12)
- `kitty-specs/stability-and-hygiene-hardening-2026-04-01KQ4ARB/contracts/tracker-public-imports.md`
  ("Auth transport adoption (FR-030)")
- `tests/architectural/test_auth_transport_singleton.py`

## Context

Before this mission, every HTTP-using subsystem inside `specify_cli`
implemented its own auth handling:

- `src/specify_cli/tracker/saas_client.py` instantiated `httpx.Client`
  directly, ran its own `_force_refresh_sync()` bridge, and handled
  401 retry-once locally.
- `src/specify_cli/auth/http/transport.py` exposed an async-only
  `OAuthHttpClient` with similar refresh semantics.
- The websocket client at `src/specify_cli/sync/client.py` consumed
  the token via `provision_ws_token()` but then maintained its own
  reconnect/backoff loop.

The result was three implementations of "401 → refresh → retry" with
three different log paths. When refresh failed, each subsystem printed
its own user-facing line, producing the duplicate-message symptom that
FR-029 / NFR-007 explicitly prohibits (≤ 1 user-facing token-refresh
failure line per command invocation).

The contract for `spec-kitty-tracker.bidirectional_sync()` (frozen in
`contracts/tracker-public-imports.md`) further mandates that
`TrackerClient` MUST acquire its HTTP transport from a single
spec-kitty-side surface. That contract is the load-bearing test for the
boundary defined in this ADR.

## Decision

A new module — `src/specify_cli/auth/transport.py` — is the single
owner of authenticated HTTP transports inside `specify_cli`.

### Public surface

- `AuthenticatedClient` (sync) wraps `httpx.Client` and performs:
  - bearer injection via the process-wide `TokenManager`,
  - 401 → forced refresh → retry-once,
  - structured failure surface via `AuthRefreshFailed` (cause chain
    preserved on `__cause__`),
  - per-invocation user-facing failure dedup (FR-029, NFR-007) keyed
    on a module-level boolean.
- `AsyncAuthenticatedClient` is the async analog; today it delegates
  to the existing `OAuthHttpClient` and shares the dedup state.
- `get_client()` / `get_async_client()` are process-scoped singleton
  accessors with double-checked-locking init.
- `AuthRefreshFailed` extends `AuthenticationError` with a stable
  `error_code` so structured logging / SaaS sync surfaces can branch
  on it without string-matching the message.

### Architectural enforcement

`tests/architectural/test_auth_transport_singleton.py` walks
`src/specify_cli/sync/`, `src/specify_cli/tracker/`, and
`src/specify_cli/auth/websocket/` with `ast`, asserting that NO module
under those subsystems contains a direct `httpx.Client(...)` or
`httpx.AsyncClient(...)` constructor call. The only allowlisted modules
are `src/specify_cli/auth/transport.py` (this ADR's home) and
`src/specify_cli/auth/http/transport.py` (the SaaS-fallback layer the
new transport delegates to).

The architectural test also includes a negative-control case that
synthesizes a forbidden call into `tmp_path` and asserts the scanner
flags it. This guards against silent passes when the AST shape changes
under us.

### Token-refresh log dedup (FR-029, NFR-007)

`AuthenticatedClient` emits at most one user-facing token-refresh
failure line per process invocation. Subsequent failures within the
same command are accumulated to a debug log only. The dedup state
lives at module scope (`_user_facing_failure_emitted`) because CLI
processes are short-lived; a long-running daemon would need
per-request scoping which is explicitly out of scope here (see
`tasks/WP06-sync-and-auth.md` Risks).

## Consequences

### Required of every new HTTP-using subsystem

Any new code path that opens an authenticated HTTP connection MUST
acquire its client via `from specify_cli.auth.transport import
get_client` (or the async accessor). Direct `httpx.Client(...)` calls
in the walked subsystems will fail
`tests/architectural/test_auth_transport_singleton.py` at CI time and
block the merge.

If a subsystem has a legitimate need for non-authenticated HTTP (e.g.
the OAuth login flows, where there is no session yet), it must keep
its calls under `src/specify_cli/auth/flows/` — that path is outside
the walked subsystems by construction. New top-level subsystems that
need HTTP MUST either:

- import `get_client()` and route through it, or
- get explicit allowlist entries in
  `tests/architectural/test_auth_transport_singleton.py` with an
  accompanying ADR amendment.

### Operator-visible behavior

- `spec-kitty sync now`, `spec-kitty tracker run`, and websocket
  reconnection paths all emit at most one "Authentication expired"
  line per command invocation.
- `AuthRefreshFailed` is a structured error type carrying an
  `error_code` (`refresh_token_invalid`, `post_refresh_401`,
  `not_authenticated`, `refresh_no_token`, `refresh_unexpected`),
  enabling downstream tooling to differentiate failure modes without
  string-matching.

### Test impact

The existing tracker tests under `tests/sync/tracker/` continue to
work unchanged: their autouse conftest patches the legacy
`_fetch_access_token_sync` / `_force_refresh_sync` module-level
helpers, which are still called by `SaaSTrackerClient._request` for
backward compatibility (the helpers fetch the token; the architectural
boundary is enforced at the *transport* layer via
`request_with_fallback_sync`).

## Alternatives considered

1. **Adopt a third-party auth library** (e.g. `httpx-auth`,
   `requests-oauthlib`). Rejected — introduces a new dependency, and
   the existing httpx-based stack already provides every primitive we
   need.
2. **Per-client refresh with a shared `TokenManager`** (status quo).
   Rejected — that is the existing bug. The single refresh lock
   inside `TokenManager` already prevents thundering-herd refreshes,
   but the absence of a single transport boundary still meant three
   different log paths and three different 401-retry implementations.
3. **Move sync into the auth subsystem entirely.** Rejected as too
   invasive for this mission; the sync subsystem is large and owns
   its own routing semantics. The narrower change here (centralize
   the *transport*, leave the routing in place) is sufficient to
   close FR-030 and pin the invariant in CI.

## References

- ADR `2026-04-19-1-cli-auth-uses-encrypted-file-only-session-storage.md` —
  underlying session storage decision.
- ADR `2026-04-09-2-cli-saas-auth-is-browser-mediated-oauth-not-password.md` —
  underlying auth flow.
- Mission `stability-and-hygiene-hardening-2026-04-01KQ4ARB`,
  `tasks/WP06-sync-and-auth.md` — implementation tasks T032 through
  T038.
