---
work_package_id: WP02
title: Diagnostic for a silently-normalized unresolvable directive token (#4240)
dependencies: []
requirement_refs:
- C-001
- C-003
- FR-003
- FR-004
- NFR-002
- NFR-003
planning_base_branch: fix/charter-directive-resolution-hardening
merge_target_branch: fix/charter-directive-resolution-hardening
branch_strategy: Planning artifacts for this mission were generated on fix/charter-directive-resolution-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/charter-directive-resolution-hardening unless the human explicitly redirects the landing branch.
subtasks:
- T005
- T006
- T007
history:
- created by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent:
- tests/charter/test_directive_unresolved_token_warning.py
execution_mode: code_change
model: sonnet
owned_files:
- src/charter/activation/resolver.py
- tests/charter/test_directive_unresolved_token_warning.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned profile: run
`/ad-hoc-profile-load python-pedro` (or `spec-kitty agent profile show python-pedro`)
and operate under it — TDD/red-first, type-safe, idiomatic Python 3.11+.

## Objective

Surface a per-token WARNING when the delivered directives service best-effort normalizes
a **fully-unresolvable** activation token, so a stale/mistyped `activated_directives`
entry no longer resolves silently — **without changing the resolution result**
(issue #4240, epic #2519).

## Context

In `src/charter/activation/resolver.py`, the `directives` property loop resolves each
activated token via `resolve_artifact_urn`; on `except UnknownArtifactIdError` it does:

```python
activated.add(token if token in all_directives else normalize_directive_id(token))
```

The `else normalize_directive_id(token)` branch is the **fully-unresolvable** path: the
token is neither URN-resolvable nor a known catalog id, so it is best-effort normalized
(e.g. `007-ghost` → `DIRECTIVE_007`) and can silently co-activate an unrelated directive.
This is legacy-compat behavior; the gap is observability, not correctness — so emit a
signal, **do not** change what gets activated (C-003).

## Guidance per subtask

### T005 — Emit the WARNING on the unresolved fallback
- Use module logging: `logging.getLogger(__name__).warning(...)` (match sibling modules;
  do not `print`).
- Fire it **only** on the `else normalize_directive_id(token)` branch — i.e. only when
  `token not in all_directives`. Do NOT warn on the `token in all_directives` sub-branch
  (that is a resolvable known id) and do NOT warn when `resolve_artifact_urn` succeeds.
- Message names both the raw token and the normalized form, e.g.
  `"unresolved directive activation token %r; best-effort normalized to %r"`, token, normalized.
- The resolution result (`activated` set) is unchanged — the warning is added alongside
  the existing `activated.add(...)`, not in place of it.

### T006 — caplog test  (red-first)
- New file `tests/charter/test_directive_unresolved_token_warning.py` (pytestmark to
  match siblings; reuse the `build_activation_aware_doctrine_service` /
  `DoctrineService(...).directives` pattern from
  `tests/charter/test_resolver_directive_activation_keying.py`).
- With `caplog.at_level(logging.WARNING)`:
  - **Unresolvable token** (names no real directive) → exactly one WARNING naming the
    token + normalized form; assert it fires (RED before T005).
  - **Resolvable token** (by filename stem, exact declared id, or a known catalog id)
    → **no** warning emitted.
  - In both cases assert the delivered `.directives` set is what it was before (outcome
    unchanged).

### T007 — No-outcome-change + quality
- Run the resolver guardrails:
  `PWHEADLESS=1 SPEC_KITTY_ENABLE_SAAS_SYNC=0 uv run --no-sync python -m pytest tests/charter/test_resolver_directive_activation_keying.py tests/charter/test_resolver_activation_gating.py tests/charter/test_directive_identity_mapping.py -q`
- `ruff check` + `ruff format --check` + `mypy` clean on `resolver.py` and the new test;
  keep the `directives` property ≤15 complexity (extract a tiny helper if the branch push
  it over).

## Branch Strategy

Planning/base branch: `fix/charter-directive-resolution-hardening`. Final merge target
for this mission's lane consolidation: `fix/charter-directive-resolution-hardening` (the
PR then targets `main`). The execution worktree is allocated from the computed lane in
`lanes.json` — enter the resolved workspace, do not reconstruct it.

## Definition of Done

- FR-003, FR-004 satisfied: WARNING on the fully-unresolvable fallback only; silent when
  the token resolves.
- C-001 / C-003: resolution result unchanged (the warning is a signal, not a gate).
- NFR-002: `tests/charter/` outcome tests unchanged (green).
- NFR-003: ruff/format/mypy clean; complexity ≤15; the new branch has a focused caplog test.

## Risks / reviewer guidance

- **Over-warning** — reviewer: confirm no warning on the `token in all_directives`
  sub-branch or on the `resolve_artifact_urn` success path (FR-004). A warning on every
  resolution would be noise.
- **Outcome drift** — reviewer: confirm `activated` membership is identical pre/post; the
  warning must not alter what is co-activated.
