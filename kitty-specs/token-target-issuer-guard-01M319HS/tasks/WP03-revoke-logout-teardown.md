---
work_package_id: WP03
title: Revoke + logout teardown
dependencies:
- WP01
requirement_refs:
- FR-002
- FR-005
- FR-008
- FR-009
- NFR-001
- NFR-004
- NFR-006
planning_base_branch: issue-4755-token-target-issuer-guard
merge_target_branch: issue-4755-token-target-issuer-guard
branch_strategy: Planning artifacts for this mission were generated on issue-4755-token-target-issuer-guard. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4755-token-target-issuer-guard unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-token-target-issuer-guard-01M319HS
base_commit: 245c0bce88192081c2791d4adf62fd88ae9732af
created_at: '2026-09-21T07:11:31.875142+00:00'
subtasks:
- T011
- T012
- T013
- T014
history:
- Created by /spec-kitty.tasks (#4755)
agent_profile: python-pedro
authoritative_surface: src/specify_cli/auth/
create_intent:
- tests/auth/test_revoke_issuer_mismatch.py
- tests/cli/test_auth_logout_mismatch.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/auth/flows/revoke.py
- src/specify_cli/cli/commands/_auth_logout.py
- tests/auth/test_revoke_issuer_mismatch.py
- tests/cli/test_auth_logout_mismatch.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Load your assigned profile before anything else: `/ad-hoc-profile-load python-pedro`. Adopt its identity,
boundaries, and governance scope for this work package.

## Objective

Make `auth logout` send the refresh-token revocation only to the issuing host, refuse (without sending)
on mismatch, and still tear down the local session so the user is never stranded logged-in.

## Context

Read: `contracts/issuer-target-helper.md`, `research.md` (D-4). Current state:
- `auth/flows/revoke.py:43` — `saas_url = get_saas_base_url()`; `RevokeFlow.revoke` **never raises**, it
  returns a `RevokeOutcome` enum; a bare `except Exception` at `:56` maps failures to `SERVER_FAILURE`.
  It POSTs `token=session.refresh_token` to `/oauth/revoke`.
- `cli/commands/_auth_logout.py:60-69` — non-force branch calls `RevokeFlow().revoke(session)` and
  reports; local credential deletion happens regardless of a server failure ("Local credentials will
  still be deleted").

### T011 — Revoke: `RevokeOutcome.ISSUER_MISMATCH`, guard before the try
- Add `ISSUER_MISMATCH` to `RevokeOutcome` (docstring: refused — resolved target ≠ session issuer; no
  POST issued).
- Resolve the endpoint via `resolve_token_endpoint(session)` **before** the `try` block, so a mismatch
  (or split-brain) is NOT folded into `SERVER_FAILURE` by the `except`. On a mismatch/split-brain return
  `ISSUER_MISMATCH` and do not build/POST the URL. On success use the resolved endpoint (no
  `get_saas_base_url()`).

### T012 — `_auth_logout`: teardown proceeds + specific warning
- On `ISSUER_MISMATCH`, print a warning naming the issuer host, the resolved host, and the remedy
  (token-free), stating server-side revocation was skipped so the user can rotate via the real server —
  then **still tear down the local session** (delete local credentials), matching the existing
  server-failure teardown posture (US2 AC5).

### T013 — Red-first repros
- `tests/cli/test_auth_logout_mismatch.py`, `@pytest.mark.regression` `#4755`:
  - consequence 1: session issuer = config-only self-hosted host → logout revoke targets the issuer host
    (not the default).
  - consequence 2: session issuer = `team.spec-kitty.ai`, `SPEC_KITTY_SAAS_URL = attacker` → logout
    refuses (no POST to attacker) and local teardown still happens.
  RED before the fix, green after.

### T014 — Revoke/logout unit
- `tests/auth/test_revoke_issuer_mismatch.py`: mismatch → `RevokeOutcome.ISSUER_MISMATCH`, no HTTP call
  made (assert the client is never invoked); issuer == target → normal revoke path unchanged (NFR-005);
  refusal diagnostic token-free (NFR-006).
- Flow-level legacy-null (US1-AC4): a session with `issuer_url = None` and a config-only self-hosted host
  → revoke targets the config host with no refusal. The helper test (WP01 T003) is the primary coverage;
  this is the flow-level confirmation.

## Branch Strategy
Planning base + local merge target: `issue-4755-token-target-issuer-guard`. Execution worktree is the
per-lane worktree from `lanes.json` via `spec-kitty implement WP03`. Depends on WP01.

## Definition of Done
- `revoke.py` no longer calls `get_saas_base_url()`; guard is before the `try`; `ISSUER_MISMATCH` added.
- Logout tears down local creds on mismatch and warns (token-free) that revoke was skipped.
- T013 RED before / green after; T014 green.
- `ruff`/`ruff format`/`mypy` clean; complexity ≤ 15; new branches covered in the same commit.

## Risks
- **Guard inside the try** — the `except Exception` would demote the mismatch to `SERVER_FAILURE`, losing
  the specific remedy. Guard BEFORE the try.
- **Stranding the user** — refusing the revoke must not also skip local teardown.

## Reviewer guidance (reviewer-renata)
Confirm no POST fires on mismatch (client never called), local teardown still runs, the warning is
specific + token-free, and the happy path is unchanged.
