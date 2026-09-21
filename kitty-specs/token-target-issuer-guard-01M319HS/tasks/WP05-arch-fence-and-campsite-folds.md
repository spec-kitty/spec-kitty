---
work_package_id: WP05
title: Arch fence + display unification + campsite folds
dependencies:
- WP01
- WP02
- WP03
- WP04
requirement_refs:
- FR-007
- FR-010
- FR-011
- NFR-003
planning_base_branch: issue-4755-token-target-issuer-guard
merge_target_branch: issue-4755-token-target-issuer-guard
branch_strategy: Planning artifacts for this mission were generated on issue-4755-token-target-issuer-guard. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4755-token-target-issuer-guard unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-token-target-issuer-guard-01M319HS
base_commit: c1f6c747c9f614f3f949e6abe5ad880e56ff0d95
created_at: '2026-09-21T07:56:13.351247+00:00'
subtasks:
- T018
- T019
- T020
- T021
- T022
- T023
history:
- Created by /spec-kitty.tasks (#4755)
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- tests/cli/test_auth_login_mismatch_exit.py
- tests/cli/test_auth_saas_target_cleanup.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/cli/commands/_auth_saas_target.py
- src/specify_cli/cli/commands/_auth_login.py
- src/specify_cli/auth/config.py
- tests/architectural/test_egress_consent_boundary.py
- tests/cli/test_auth_login_mismatch_exit.py
- tests/cli/test_auth_saas_target_cleanup.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Load your assigned profile before anything else: `/ad-hoc-profile-load python-pedro`. Adopt its identity,
boundaries, and governance scope for this work package.

## Objective

Prevent recurrence by construction (a non-vacuous architectural fence on `get_saas_base_url()`), unify
the last parallel guard (the display consumer), and fold the two same-seam campsite findings. This WP
lands **last** — the fence can only go green once WP02–WP04 have rewired all four token-send flows off
`get_saas_base_url()`.

## Context

Read: `contracts/issuer-target-helper.md` (fence contract), `research.md` (D-6, scope). Facts:
- `tests/architectural/test_egress_consent_boundary.py` already carries E18 "token traffic, no project
  data" allowances for refresh.py, revoke.py, websocket/token_provisioning.py, and auth/http/transport.py
  — extend this file; do not create a parallel gate.
- `cli/commands/_auth_saas_target.py` — `format_saas_mismatch_warning` (~`:138`) RETURNS a display string
  and has a duplicate `_normalize_endpoint` (~`:157`); it also has the #4053 dead
  `except ConfigurationError` branch (~`:66`) + its import (~`:18`) and a mislabeled no-opinion-default
  provenance (~`:120`).
- `cli/commands/_auth_login.py` — the resolver+issuer exemplar; #4265: mismatch refusal returns exit 0
  (~`:131`) and a raw `url != DEFAULT_HOSTED_SAAS_URL` label comparison (~`:206`).

### T018 — Fence, forbidden set + allowlist floor + self-mutation
- Extend `test_egress_consent_boundary.py` so referencing `get_saas_base_url` from any token-send module
  (`auth/flows/refresh.py`, `auth/flows/revoke.py`, `auth/token_manager.py`, `auth/websocket/token_provisioning.py`)
  FAILS. Allowlist floor (explicit): `auth/config.py` (definition), `auth/flows/device_code.py`,
  `auth/flows/authorization_code.py`, `auth/flows/client_credentials.py`, `auth/http/transport.py`, and
  the display/doctor surfaces already on `resolve_server_target`. Include a self-mutation direction: the
  gate fails when a token-send module regains the call.

### T019 — Fence, second vacuity direction
- Add an assertion that the allowlist provably EXCLUDES the four token-send modules — the gate fails if
  any of them is added to the allowlist (no vacuous whitelist). NFR-003.

### T020 — Display consumer unification + config docstring
- Refactor `format_saas_mismatch_warning` to consume WP01's shared decision (render the verdict as a
  display string; it must KEEP RETURNING, not raise — `auth login`/`status`/`doctor` render without
  aborting). Remove its duplicate `_normalize_endpoint` in favour of the canonical one (import-safe).
- Update `auth/config.py::get_saas_base_url` docstring to note it is fenced off token-send paths.

### T021 — Fold #4053
- Remove the now-unreachable `except ConfigurationError` branch and its import; correct the no-opinion
  default provenance label. Add a focused test in `tests/cli/test_auth_saas_target_cleanup.py`.

### T022 — Fold #4265
- `auth login` issuer-mismatch refusal returns a non-zero exit code; the custom-endpoint label uses a
  canonical-host comparison (not the raw `!=` against the default literal). Add
  `tests/cli/test_auth_login_mismatch_exit.py` (assert non-zero exit + correct label for a `:443` host).

### T023 — Fence + duality + membership tests
**Test homes (stay within owned_files):** put the fence both-directions + positive-membership assertions
in `tests/architectural/test_egress_consent_boundary.py` (owned); put the display-still-renders assertion
in `tests/cli/test_auth_saas_target_cleanup.py` (owned). Do not create a new test file.
- In `test_egress_consent_boundary.py`: assert the fence fails in BOTH directions (mutate a token module
  to call the accessor → RED; add a token module to the allowlist → RED) and passes for legitimate
  non-token callers. **Non-vacuity caveat** (per post-tasks review): because WP05 runs after WP02–04, the
  fence is never observed RED against the *original* leak — so wire the self-mutation and allowlist-exclusion
  tests to the **real** gate function (import and invoke it), never a copied allowlist literal, or the
  gate is vacuous.
- **Positive-membership** (SC-003), in `test_egress_consent_boundary.py`: assert the compare+normalize+remedy
  decision lives in exactly one module and each of the six consumers (four flows +
  `saas_client._guard_session_issuer` + `format_saas_mismatch_warning`) imports/consumes it. Positive
  membership, not a "no copies" grep.
- In `test_auth_saas_target_cleanup.py`: assert `auth status` / `auth doctor` still RENDER an issuer
  mismatch (display string, no exception).

## Branch Strategy
Planning base + local merge target: `issue-4755-token-target-issuer-guard`. Execution worktree is the
per-lane worktree from `lanes.json` via `spec-kitty implement WP05`. Depends on WP01–WP04 (the fence is
only green once all flows are rewired).

## Definition of Done
- Fence fails in both directions and passes for allowlisted non-token callers; display path still renders;
  positive-membership holds.
- #4053 and #4265 folded with focused tests; `config.py` docstring updated.
- `ruff`/`ruff format`/`mypy` clean; complexity ≤ 15; new branches covered in the same commit.

## Risks
- **Landing before the flows are rewired** → the fence goes RED on a legitimately-still-leaking module.
  This WP depends on WP02–WP04; do not start the fence subtasks until they are merged into the lane base.
- **Turning the display path into a raise** → breaks `auth status`/`doctor`. Keep `format_saas_mismatch_warning`
  returning a string.
- **Fold creep** — keep #4053/#4265 to the exact lines the unification already rewrites; anything larger
  is a PR follow-up note, not scope.

## Reviewer guidance (reviewer-renata)
Verify the fence is non-vacuous in both directions, the display duality is preserved, positive-membership
is asserted, and the folds are bounded to the touched lines.
