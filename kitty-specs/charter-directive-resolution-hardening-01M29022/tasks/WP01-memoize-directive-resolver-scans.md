---
work_package_id: WP01
title: Memoize directive resolver filesystem scans (#4239)
dependencies: []
requirement_refs:
- C-001
- C-002
- FR-001
- FR-002
- NFR-001
- NFR-002
- NFR-003
planning_base_branch: fix/charter-directive-resolution-hardening
merge_target_branch: fix/charter-directive-resolution-hardening
branch_strategy: Planning artifacts for this mission were generated on fix/charter-directive-resolution-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/charter-directive-resolution-hardening unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-charter-directive-resolution-hardening-01M29022
base_commit: eae5793dbaeeb57c7b4589ec1fc81560a38ee473
created_at: '2026-09-11T19:58:45.257619+00:00'
subtasks:
- T001
- T002
- T003
- T004
history:
- created by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/activation/
create_intent:
- tests/charter/test_directive_resolution_memoization.py
execution_mode: code_change
model: sonnet
owned_files:
- src/charter/activation/kind_vocabulary.py
- tests/charter/test_directive_resolution_memoization.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned profile: run
`/ad-hoc-profile-load python-pedro` (or `spec-kitty agent profile show python-pedro`)
and operate under it — TDD/red-first, type-safe, idiomatic Python 3.11+.

## Objective

Cut the O(D×S) filesystem work in directive resolution so a single resolution pass
walks each doctrine layer once, **without changing any resolution outcome** and
**without introducing a second ordering** (issue #4239, epic #2519).

## Context

In `src/charter/activation/kind_vocabulary.py`:
- `resolve_config_id` (directive branch) iterates candidate paths and, per stem,
  calls `resolve_artifact_urn` for the round-trip/representability check.
- `resolve_artifact_urn` re-invokes `_iter_artifact_paths`, which `rglob`s every
  doctrine layer — so the same layers are re-walked once per stem.
- `_directive_ids_by_stem(paths, id_field, yaml)` already builds a stem→{ids} map
  over one path list; reuse this shape.
- `_iter_artifact_paths` returns the authoritative **high→low** precedence order
  (project → org packs last-declared-first → built-in). This ordering is the single
  authority — **do not** add a second sort/reverse (C-002; this is exactly the bug
  #4194 fixed, do not regress it).

## Guidance per subtask

### T001 — Memoize the per-layer scan
- Add a memo of `_iter_artifact_paths(kind, doctrine_root, org_roots, layer_roots)`
  keyed on the resolved inputs plus each scanned directory's `mtime_ns`
  (`Path.stat().st_mtime_ns`), so a repeated call with unchanged inputs and unchanged
  on-disk mtimes returns the cached path list. A resolution-pass-scoped memo is an
  acceptable simpler alternative if a module-level `(path, mtime)` cache proves fiddly
  — but a *later* resolution (new service / new call after a file change) MUST observe
  the change (FR-002).
- Keep the returned order exactly as `_iter_artifact_paths` produces it. The memo
  caches output; it never reorders (C-002).

### T002 — Route the memo through the round-trip
- Ensure `resolve_config_id`'s directive round-trip (its per-stem `resolve_artifact_urn`)
  and `_directive_ids_by_stem` consume the memoized scan, so N stems over L layers do
  L scans, not N×L. Do not change the round-trip's representability/ambiguity logic
  (that is the #4194 contract).

### T003 — Scan-count + mtime test  (red-first)
- New file `tests/charter/test_directive_resolution_memoization.py` (pytestmark to
  match siblings, e.g. `[pytest.mark.fast, pytest.mark.corpus]` if it reads the real
  corpus, else `pytest.mark.fast`).
- Introduce a **counted-scan seam** (e.g. wrap/patch the directory enumeration or count
  `rglob`/`iterdir` calls) and assert: a single `resolve_config_id` pass over an
  L-layer fixture performs ≤ L layer scans (RED before T001/T002).
- Assert mtime invalidation: after changing a file's content (bump mtime), a fresh
  resolution observes the new content.
- Keep it a real red→green: confirm the scan-count assertion fails against pre-memo
  code, passes after.

### T004 — No-outcome-change + quality
- Run the resolution-outcome guardrails green:
  `PWHEADLESS=1 SPEC_KITTY_ENABLE_SAAS_SYNC=0 uv run --no-sync python -m pytest tests/charter/test_directive_identity_mapping.py tests/charter/test_resolver_directive_activation_keying.py tests/charter/test_drg_activation_gate.py tests/charter/test_resolver_activation_gating.py -q`
- `ruff check` + `ruff format --check` + `mypy` clean on `kind_vocabulary.py` and the
  new test; keep any touched function ≤15 complexity.

## Branch Strategy

Planning/base branch: `fix/charter-directive-resolution-hardening`. Final merge target
for this mission's lane consolidation: `fix/charter-directive-resolution-hardening`
(the PR then targets `main`). The execution worktree for this WP is allocated from the
computed lane in `lanes.json` — enter the resolved workspace, do not reconstruct it.

## Definition of Done

- FR-001, FR-002 satisfied: ≤1 scan/layer/pass, mtime-correct invalidation.
- NFR-002: `tests/charter/` outcome tests unchanged (green).
- NFR-003: ruff/format/mypy clean; complexity ≤15; the new branch/helper has a focused test.
- C-002 preserved: no second ordering; `_iter_artifact_paths` remains the sole precedence authority.

## Risks / reviewer guidance

- **Ordering regression** — the memo must cache, never reorder. Reviewer: confirm no new
  `sort`/`reverse` and that #4194's identity/ambiguity tests still pass.
- **Stale cache** — reviewer: confirm the mtime key (or pass-scoping) makes a post-change
  resolution observe new content; a global cache without invalidation is a defect.
