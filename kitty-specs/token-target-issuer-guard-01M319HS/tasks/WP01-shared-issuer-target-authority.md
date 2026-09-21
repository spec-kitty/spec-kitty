---
work_package_id: WP01
title: Shared issuer-target authority (foundation)
dependencies: []
requirement_refs:
- FR-005
- FR-006
- FR-007
- FR-012
- NFR-002
- NFR-006
- C-001
- C-002
planning_base_branch: issue-4755-token-target-issuer-guard
merge_target_branch: issue-4755-token-target-issuer-guard
branch_strategy: Planning artifacts for this mission were generated on issue-4755-token-target-issuer-guard. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-4755-token-target-issuer-guard unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-token-target-issuer-guard-01M319HS
base_commit: 3a2d9a805b25020415bfd5b86f7c5b0d149c72c3
created_at: '2026-09-21T06:47:29.092848+00:00'
subtasks:
- T001
- T002
- T003
history:
- Created by /spec-kitty.tasks (#4755)
agent_profile: python-pedro
authoritative_surface: src/specify_cli/auth/
create_intent:
- tests/auth/test_issuer_target_helper.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/auth/server_target.py
- src/specify_cli/auth/errors.py
- tests/auth/test_issuer_target_helper.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned profile: run `/ad-hoc-profile-load python-pedro`
(or the `spk-doctrine-profile-load` skill with `python-pedro`). Adopt its identity, boundaries, and
governance scope for this entire work package. Do not act as a generic agent.

## Objective

Create the **single canonical authority** for the resolve-target-and-guard-issuer decision that every
token-bearing flow (WP02–WP04) and the display/guard consumers (WP05, and the existing `saas_client`
guard adopted in WP02) will consume. This WP creates the helper and its typed error only — no consumer
wiring. It is the foundation the rest of the mission depends on.

## Context

Read first: `kitty-specs/token-target-issuer-guard-01M319HS/spec.md`,
`plan.md` (Architecture section), and `contracts/issuer-target-helper.md` (the authoritative contract).

The canonical pattern already exists as `saas_client/auth.py::_guard_session_issuer` (compare normalized
`session.issuer_url` vs `resolve_server_target(process_wide_override=False).resolved_server_url`; pass
through `issuer_url=None`; refuse on mismatch). This WP lifts that rule into ONE reusable authority so we
never grow a 3rd/4th parallel copy. `auth/server_target.py` already owns `resolve_server_target`,
`ResolvedServerTarget`, and `_normalize_url` (line ~98) — home the new code there and reuse that
normalizer for BOTH the comparison and the returned endpoint (NFR-002: no divergent normalization).

### Subtask T001 — `IssuerTargetMismatchError` in `auth/errors.py`
Add an `AuthenticationError` subclass carrying:
- `issuer_url: str`, `resolved_url: str`, `remedy: str` (a **stable** identifier, e.g. the module
  constant `ISSUER_MISMATCH_REMEDY = "auth login --force"`).
- A message that names the issuer host, the resolved host, the config source, and the remedy — and
  contains **zero token material** (NFR-006). Keep the message construction here (or in the helper) so
  callers never interpolate a token.
Confirm `AuthenticationError` is the right base (it is the shared root the flows already raise under).

### Subtask T002 — issuer decision + `resolve_token_endpoint(session)` in `auth/server_target.py`
Implement per `contracts/issuer-target-helper.md`:
- Separate the **decision** from the **reaction** so a display consumer (WP05) can render the verdict
  without raising. Suggested shape: a small internal `_issuer_target_decision(session) -> tuple` (or a
  frozen verdict dataclass) returning `(endpoint, mismatch_or_None)`, plus the public raise-based
  wrapper `resolve_token_endpoint(session: StoredSession | None) -> str`:
  1. `target = resolve_server_target(process_wide_override=False)` (let `ServerTargetSplitBrainError`
     propagate — callers map it).
  2. `session is None` or `session.issuer_url is None` → return `_normalize_url(target.resolved_server_url)`
     (legacy/no-compare; **never** `get_saas_base_url()`).
  3. else compare `_normalize_url(session.issuer_url)` vs `_normalize_url(target.resolved_server_url)`;
     equal → return the normalized resolved target; differ → raise `IssuerTargetMismatchError`.
- Reuse `_saas_source_name`-style provenance naming if useful for the message (keep local; do not import
  a CLI-presentation helper). Keep complexity ≤ 15 (extract helpers if needed).
- Do NOT change `resolve_server_target` precedence or the packaged default (C-002).

### Subtask T003 — helper unit tests (`tests/auth/test_issuer_target_helper.py`, new)
Deterministic, network-free (monkeypatch `resolve_server_target` / env / config). Cover:
- issuer == target → returns the normalized endpoint (assert trailing-slash/whitespace normalized).
- issuer != target → raises `IssuerTargetMismatchError`; assert `issuer_url`, `resolved_url`, `remedy`
  fields and that `str(exc)` contains neither the access nor refresh token fixture value (NFR-006).
- `issuer_url = None` (legacy) and `session = None` → returns the resolved target, no raise, and is NOT
  the packaged default when config names a different host (FR-006, FR-012).
- split-brain → `ServerTargetSplitBrainError` propagates (not swallowed, not misclassified).

## Branch Strategy

Planning base and local merge target: `issue-4755-token-target-issuer-guard` (the PR later lands this on
`main`). Execution runs in the per-lane worktree resolved from `lanes.json` by `spec-kitty implement WP01`
— do not hand-create a branch or worktree.

## Definition of Done
- `resolve_token_endpoint` + `IssuerTargetMismatchError` exist per the contract; the one normalizer is
  reused for compare + endpoint.
- All T003 cases pass; new branches are covered by focused tests in the same commit.
- `ruff check`, `ruff format --check`, `mypy` clean on the touched files; complexity ≤ 15 (NFR-007).
- No consumer is rewired in this WP (that is WP02–WP05).

## Risks
- **Normalizer drift** — using anything other than `server_target._normalize_url` re-opens the leak. Reuse it.
- **Over-coupling the display path** — keep the decision separable from the raise so WP05 can render it.

## Reviewer guidance (reviewer-renata)
Verify the None/legacy path never reaches `get_saas_base_url`; the error message is token-free; the
decision/reaction split is present; and complexity/static gates hold.
