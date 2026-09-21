# Research: Auth token-target issuer guard (#4755)

No open `[NEEDS CLARIFICATION]`. This record consolidates a 3-lens opus grounding squad + a post-spec
adversarial lens; every decision below was contested and resolved (per the adversarial-evidence posture).

## D-1 — Canonical helper home: the `auth` package (`server_target.py`)
- **Decision**: home `resolve_token_endpoint(session)` and the issuer decision in
  `src/specify_cli/auth/server_target.py`, reusing its in-module `resolve_server_target` and
  `_normalize_url`.
- **Rationale**: the issuer/target rule is auth-subsystem semantics; server_target.py already owns every
  dependency (resolver, normalizer, `SAAS_URL_ENV_VAR`). `saas_client` already imports `server_target`
  freely and there is no LayerRule between sub-packages of `specify_cli`, so `saas_client` consuming it
  is the existing, legal pattern. CLAUDE.md's "saas_client is a client of upstream" governs API *shape*,
  not an import ban.
- **Alternatives**: a new top-level module (rejected — needless surface, would re-export the private
  normalizer); homing in `saas_client` (rejected — wrong bounded context, and login/status/doctor would
  have to reach into a client module).
- **Disposition**: accepted.

## D-2 — Refusal type: new `IssuerTargetMismatchError(AuthenticationError)`
- **Decision**: add to `auth/errors.py`; carries issuer host, resolved host, and a stable remedy id.
- **Rationale**: `RefreshTokenExpiredError` implies the token died (wrong remedy). CRITICAL: the
  refresh-path refusal must be a type the `saas_client._usable_access_token` bare-`except` cannot demote
  to "use the held token" → add it to `_dead_session_errors()`.
- **Disposition**: accepted (adversarial M4 reinforced: the guard must gate the *send*, so the held-token
  fast path that returns a still-valid token is covered too).

## D-3 — Guard/resolve at the TokenManager boundary for refresh
- **Decision**: resolve + guard before entering `run_refresh_transaction` / the machine lock.
- **Rationale**: refresh runs in-lock; resolving inside risks `ServerTargetSplitBrainError` entering an
  error contract the in-lock flow does not express, and holding the lock across a raise.
- **Disposition**: accepted.

## D-4 — Per-flow refusal adapters (refusal must not be swallowed into a send)
- refresh: raise (in `_dead_session_errors`), guard before POST.
- revoke: never raises → `RevokeOutcome.ISSUER_MISMATCH`, guard before the `try`; local teardown still
  proceeds on logout, user warned server revoke was skipped.
- rehydrate: best-effort → fail-closed no-op + **specific** warning (hosts + remedy); not upgraded to a
  hard raise (would break otherwise-working sessions).
- ws: wrap into `WebSocketProvisioningError`; guard before URL build and `get_access_token`.
- **Disposition**: accepted (adversarial M3: split-brain collapses into the same non-leak posture on all
  flows; logout local teardown explicitly proceeds).

## D-5 — Legacy `issuer_url = None` → resolved target, no refusal
- **Decision**: route to `resolve_server_target(...).resolved_server_url` (honours config.toml); no
  compare, no refusal, never the packaged default.
- **Rationale**: otherwise legacy self-hosted sessions keep leaking to the default host.
- **Disposition**: accepted.

## D-6 — Preserve the display-vs-raise duality on unification
- **Decision**: the shared *decision* returns a verdict; `resolve_token_endpoint` is the raise wrapper
  for the four flows + `saas_client`; `_auth_saas_target.format_saas_mismatch_warning` renders the same
  verdict as a display string (keeps RETURNING, does not start raising).
- **Rationale**: `auth login`/`status`/`doctor` render the warning without aborting; collapsing them onto
  a raise-based helper would break the display path.
- **Disposition**: accepted (adversarial M1 — highest-value catch).

## Scope decisions
- Closes **#4755** only. Fold **#4053** (dead `except ConfigurationError` branch + import + provenance
  label in `_auth_saas_target.py`) and **#4265** (auth login mismatch exit code + canonical-URL
  comparison) as same-seam campsite, only on lines the unification already rewrites.
- **Dormant ws** (Path 4): no caller since the sync transport retired → defence-in-depth; verified by
  direct invocation, not an integration reproduction (adversarial M5).
- Kept SEPARATE: #2941, #3279, local-write-safety siblings (#4756/#4757/#4812), #4760, dashboard-trust
  epic. Parent #4755 under epic **#3892** for tracking (operator tracker action).

## Supply chain
No dependency added/upgraded/removed → supply-chain planning gate not engaged.
