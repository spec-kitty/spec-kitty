---
work_package_id: WP02
title: TokenManager wiring (refresh + rehydrate) + held-token non-demotion
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-003
- FR-005
- FR-008
- FR-009
- NFR-001
- NFR-004
- NFR-005
- NFR-006
planning_base_branch: issue-4755-token-target-issuer-guard
merge_target_branch: issue-4755-token-target-issuer-guard
branch_strategy: Planning artifacts for this mission were generated on issue-4755-token-target-issuer-guard. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4755-token-target-issuer-guard unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-token-target-issuer-guard-01M319HS
base_commit: a3327d89e08835ab0c1a6f64d938c7c02565346b
created_at: '2026-09-21T07:08:26.189355+00:00'
subtasks:
- T004
- T005
- T006
- T007
- T008
- T009
- T010
history:
- Created by /spec-kitty.tasks (#4755)
agent_profile: python-pedro
authoritative_surface: src/specify_cli/auth/
create_intent:
- tests/auth/test_refresh_issuer_target.py
- tests/auth/test_rehydrate_issuer_target.py
- tests/saas_client/test_held_token_non_demotion.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/auth/flows/refresh.py
- src/specify_cli/auth/token_manager.py
- src/specify_cli/auth/http/me_fetch.py
- src/specify_cli/saas_client/auth.py
- tests/auth/test_refresh_issuer_target.py
- tests/auth/test_rehydrate_issuer_target.py
- tests/saas_client/test_held_token_non_demotion.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Load your assigned profile before anything else: `/ad-hoc-profile-load python-pedro`. Adopt its identity,
boundaries, and governance scope for this work package.

## Objective

Wire the **refresh** and **membership rehydrate** paths to the session's issuer via
`resolve_token_endpoint` (WP01), guard at the **TokenManager boundary**, and close the **held-token
swallow re-leak** in `saas_client`. This WP owns the two most exploitable live consequences on the
access/refresh token paths that route through `TokenManager` and `saas_client`.

## Context

Read: `contracts/issuer-target-helper.md`, `research.md` (D-2, D-3, D-4), and the grounding notes in
`traces/design-decisions.md`. Key files and current leak points:
- `auth/flows/refresh.py:85` — `saas_url = get_saas_base_url()`; the flow already preserves
  `issuer_url` on the new session (`:181`) but never uses it for the URL.
- `auth/token_manager.py` — `refresh_if_needed` (`:528`) runs `run_refresh_transaction` inside a
  machine lock (`:574`); `_resolve_saas_base_url` (`:426`, returns `get_saas_base_url()` at `:437`) feeds
  `rehydrate_membership_if_needed` (`:440`) → `fetch_me_payload(self._resolve_saas_base_url(), session.access_token)` (`:479`).
- `saas_client/auth.py` — `_usable_access_token` calls `refresh_if_needed()` and catches
  `_dead_session_errors()` then a bare `except Exception → use the held token` (**the re-leak trap**);
  `_guard_session_issuer` (`:242`) is the existing guard to unify onto the shared decision;
  `_dead_session_errors()` (`:343`) is the tuple that must include the mismatch error.
- `auth/http/me_fetch.py:28` — builds the URL with strip-less `rstrip("/")` (must match the guard's
  normalization exactly).

### T004 — Refresh: consume endpoint, guard at the boundary
- Resolve the endpoint via `resolve_token_endpoint(session)` and **guard at the TokenManager boundary**
  (in `refresh_if_needed`/`get_access_token`, before entering `run_refresh_transaction`), NOT deep inside
  the in-lock `TokenRefreshFlow.refresh` — so `IssuerTargetMismatchError`/`ServerTargetSplitBrainError`
  never enter the in-lock flow's error contract and the lock is never held across the raise (D-3).
- Pass the resolved base URL into `TokenRefreshFlow.refresh` (thread it as a parameter) so `refresh.py`
  no longer calls `get_saas_base_url()` at all.

### T005 — saas_client: non-demotion + guard unification
- Add `IssuerTargetMismatchError` to `_dead_session_errors()` so `_usable_access_token`'s first
  `except` catches it as a **hard refusal** and it never falls through to "use the held token" (FR-008).
- Confirm the held-token fast path returns/raises the refusal rather than the still-valid token when the
  issuer ≠ target (guard the **send**, not only the refresh — a valid access token must be blocked too).
- Refactor `_guard_session_issuer` to CONSUME the shared decision from WP01 (delete its duplicated
  compare/normalize/remedy logic; keep its `SaasAuthError` translation at `_oauth_session_context`).

### T006 — Rehydrate: session-threaded target + fail-closed warning
- Thread `session` into `_resolve_saas_base_url` (or resolve at the `rehydrate_membership_if_needed`
  call site where `session` is in scope) and use `resolve_token_endpoint(session)`.
- A mismatch raise is caught by the existing `except Exception → return False`; keep it a **fail-closed
  no-op** (do NOT upgrade to a hard raise — that would break otherwise-working sessions), but make the
  warning **specific**: name the issuer host, resolved host, and remedy, token-free (FR-009, NFR-006).

### T007 — `me_fetch` normalizer parity
- Replace the strip-less `rstrip("/")` with the canonical normalizer so the URL actually requested is
  byte-identical to the guarded comparison (NFR-002).

### T008 — Red-first repro: consequence 1 (self-hosted) refresh
- `tests/auth/test_refresh_issuer_target.py`, `@pytest.mark.regression` pinned `#4755`: session issuer =
  `http://127.0.0.1:PORT` configured only via `config.toml [sync].server_url`, access token expired →
  drive refresh → assert `/oauth/token` targets the configured host and the refresh token never reaches
  `team.spec-kitty.ai`. Must be RED before the fix (through `refresh_if_needed`), green after.

### T009 — Red-first repro: consequence 2 (hostile env) refresh + held-token
- `tests/saas_client/test_held_token_non_demotion.py`, `@pytest.mark.regression` `#4755`: session issuer
  = `https://team.spec-kitty.ai`, `SPEC_KITTY_SAAS_URL = http://127.0.0.1:ATTACKER` →
  (a) refresh refuses, no token to attacker; (b) `_usable_access_token` with a still-valid token does NOT
  return it for transmission on mismatch. RED before, green after.

### T010 — Rehydrate mismatch unit
- `tests/auth/test_rehydrate_issuer_target.py`: mismatch → `False` + a warning naming hosts + remedy
  (assert token fixture absent); issuer == target → rehydrate unchanged (NFR-005).
- Flow-level legacy-null (US1-AC4): a session with `issuer_url = None` and a config-only self-hosted host
  → refresh/rehydrate route to the config host with no refusal (add one refresh assertion in
  `test_refresh_issuer_target.py` too). The helper test (WP01 T003) is the primary coverage; these are the
  flow-level confirmations.

After the fix, keep the two regression repros pinned as regression only if they exercise the pre-existing
entry point end-to-end; otherwise convert to focused unit tests (do not leave transitional scaffolding
marked `regression`).

## Branch Strategy
Planning base + local merge target: `issue-4755-token-target-issuer-guard`. Execution worktree is the
per-lane worktree from `lanes.json` via `spec-kitty implement WP02`. Depends on WP01 (helper + error).

## Definition of Done
- refresh + rehydrate target the issuer or refuse; `refresh.py` and the rehydrate path no longer call
  `get_saas_base_url()`; `me_fetch` uses the canonical normalizer.
- `IssuerTargetMismatchError` is in `_dead_session_errors()`; held-token fast path cannot demote it.
- `_guard_session_issuer` consumes the shared decision (no duplicated compare logic).
- T008/T009 RED before, green after; T010 green; diagnostics token-free.
- `ruff`/`ruff format`/`mypy` clean; complexity ≤ 15; new branches covered in the same commit.

## Risks
- **In-lock error contract** — guarding inside `run_refresh_transaction` would leak a new error type into
  the lock; guard at the boundary (D-3).
- **Missing the held-token path** — fixing `refresh.py` alone re-opens the leak via `_usable_access_token`
  (T005 is load-bearing).
- **token_manager.py write scope** — this WP owns the whole file (refresh boundary + rehydrate); do not
  leave a second WP editing it.

## Reviewer guidance (reviewer-renata)
Confirm the guard is at the boundary; the mismatch is in `_dead_session_errors`; the held-token path is
blocked for a still-valid token; the rehydrate warning is specific and token-free; me_fetch normalization
matches the guard.
