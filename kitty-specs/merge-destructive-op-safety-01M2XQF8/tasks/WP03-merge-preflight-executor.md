---
work_package_id: WP03
title: Merge pre-mutation preflight + executor routing (issues 4752/4753)
dependencies:
- WP01
- WP02
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-006
- NFR-001
- NFR-002
- NFR-004
planning_base_branch: fix/merge-destructive-op-safety
merge_target_branch: fix/merge-destructive-op-safety
branch_strategy: Planning artifacts for this mission were generated on fix/merge-destructive-op-safety. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/merge-destructive-op-safety unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-merge-destructive-op-safety-01M2XQF8
base_commit: def2e53644c4445fa4415c1b06388bf5dbd03c6c
created_at: '2026-09-19T22:44:37.250481+00:00'
subtasks:
- T010
- T011
- T012
- T013
- T014
phase: Phase 1 - Implementation
history:
- at: '2026-09-19T21:10:00Z'
  actor: system
  action: Prompt generated for merge-destructive-op-safety mission
agent_profile: python-pedro
authoritative_surface: src/specify_cli/merge/
create_intent:
- tests/integration/test_merge_primary_checkout_safety.py
- tests/integration/test_merge_lane_worktree_safety.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/merge/executor.py
- src/specify_cli/merge/git_probes.py
- src/specify_cli/merge/preflight.py
- tests/integration/test_merge_primary_checkout_safety.py
- tests/integration/test_merge_lane_worktree_safety.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '4752'
- '4753'
---

# Work Package Prompt: WP03 – Merge pre-mutation preflight + executor routing

## ⚡ Do This First: Load Agent Profile

Load the `python-pedro` profile (role: implementer) via the profile-load skill
before anything else. Then read `spec.md`, `plan.md`, `research.md`,
`data-model.md`, `quickstart.md`, and both `contracts/*.md`.

## Objective

Wire the WP01 guard into the lane-based merge as a **pre-mutation preflight** that
runs BEFORE the target ref is advanced, covering both P0 data-loss bugs:
- #4752 — primary checkout must be on-target AND clean, else refuse before any
  `reset --hard`.
- #4753 — every lane + coord worktree is checked in preflight; a dirty one fails
  the merge closed (unless retention is in effect) before any cleanup runs.
This makes atomicity uniform (NFR-001): on refusal the destructive call site is
never reached and the repo is byte-identical to pre-invocation.

## Context (grounding — file:line, current main)

- Phase order in `_run_lane_based_merge` (`merge/executor.py:1815-1828`): … →
  `_phase_mission_to_target` (`:1820`, REF ADVANCE via `lanes/merge.py:899/946`) →
  `_phase_capture_and_baseline` (`:1821`, calls `_refresh_primary_checkout_after_merge`
  at `:920` — the #4752 `reset --hard`) → … → `_phase_cleanup_worktrees_and_branches`
  (`:1827`, the #4753 `worktree remove --force` at `:1606`).
- `_refresh_primary_checkout_after_merge` (`merge/git_probes.py:203`, reset at
  `:213`) — its docstring claims a clean-worktree preflight that does not exist for
  the lane path; you are adding it.
- Reuse WP01 `assert_checkout_on_target` + `assert_worktree_clean` +
  `guarded_worktree_remove` (the shared removal seam — NOT the dead
  `core/vcs/git.py remove_workspace`). Inject `is_toolchain_generated_churn`.
- **Preflight placement (brownfield scout):** insert the safety preflight in the
  OUTER `_run_lane_based_merge`, BEFORE the locked phase list runs — specifically
  before `_phase_merge_lanes` (which already git-merges lanes into the mission
  branch) and `_phase_bake_and_pre_target_done` (which commits a done-event on the
  coord branch). Only then is a refusal byte-identical to pre-invocation (NFR-001).
  At that early point `run.baseline_mission_id` is not yet set — resolve the
  mission id from `meta.json` yourself to build lane-worktree paths
  (`worktree_path(main_repo, mission_slug, mission_id=..., lane_id=...)`), and the
  coord worktree via `CoordinationWorkspace`. The lanes manifest is already loaded
  (`require_lanes_json` / `run.lanes_manifest`).
- **Retention flag:** read `run.remove_worktree` (False ⇒ retention in effect) —
  the same flag the existing cleanup guards on — so refuse and cleanup agree.
- If you add a phase, update whatever asserts the frozen `expected_order`/INV-5;
  prefer a pre-list guard call (like `_heal_pending_coord_reconcile`) that is not a
  numbered phase.
- Red-first harness template: `tests/integration/test_merge_lane_planning_data_loss.py`
  Layer 2 `_real_merge_external_mocks` (`~:346`) — real git, external side effects
  mocked.

## Subtasks

### T010 — Pre-mutation safety preflight
Add a preflight (new helper, invoked from the OUTER `_run_lane_based_merge` BEFORE
`_phase_merge_lanes` — see the placement note above; NOT at the `_phase_mission_to_target`
seam, which is already past two mutating phases) that: (a)
`assert_checkout_on_target(main_repo, target)`; (b) `assert_worktree_clean(main_repo, ...,
error_code="MERGE_UNSAFE_PRIMARY_DIRTY")` — pass PRIMARY_DIRTY for the primary checkout
(FR-002/US1 AC2; the guard now accepts a caller-chosen `error_code`, default WORKTREE_DIRTY);
(c) resolves the mission id from meta, iterates every lane + coord worktree and
`assert_worktree_clean` (default WORKTREE_DIRTY) — unless `run.remove_worktree` is False (retention), in
which case dirty worktrees are recorded for retention rather than refusal. Any
`DestructiveOpRefused` aborts the merge fail-closed with the remediation message,
before any repo mutation (byte-identical, NFR-001). Honor `--resume` identically
(AC US1.4).

### T011 — Guard the primary reset
Make `_refresh_primary_checkout_after_merge` a no-op / guarded when HEAD is not the
target branch (defense in depth), so even a bypassed preflight cannot reset an
off-target checkout. Reuse the WP01 assertion; keep behavior identical on the safe
on-target path.

### T012 — Route cleanup through the guarded seam
Replace the raw `git worktree remove --force` loop in
`_phase_cleanup_worktrees_and_branches` (the lane-worktree destroy) with calls to
WP01's `guarded_worktree_remove(..., retain=False)`. **Do NOT map the operator's
`--keep-worktree`/`retain_worktrees` into the guard's `retain` param** (review
ADVISORY-3): the existing loop only runs when `run.remove_worktree` is True
(removal requested), and `--keep-worktree` already makes `run.remove_worktree`
False → the loop is skipped and all worktrees are kept. So inside the loop, removal
IS wanted; pass `retain=False`. The T010 preflight has already fail-closed on any
dirty worktree, so `retain=False` here removes known-clean worktrees and, as
defense-in-depth against a race, refuses rather than force-destroys if one is
somehow dirty. Clean worktrees are removed exactly as today. (The coord/orchestrator
destroys are WP02; do not edit those files here.)

### T013 — Red-first #4752 (`tests/integration/test_merge_primary_checkout_safety.py`)
Using the Layer-2 harness (do NOT mock `_refresh_primary_checkout_after_merge`),
cover BOTH #4752 loss conditions:
- **Off-target (FR-001 / US1 AC1):** seed the primary checkout on a non-target
  branch with an uncommitted tracked edit.
- **On-target-but-dirty (FR-002 / US1 AC2):** seed the primary checkout ON the
  target branch with an uncommitted tracked edit — this is the core reset-loss case
  and must have its own variant.
For each: assert RED pre-fix (edit destroyed / `SafeCommitHeadMismatch`), GREEN
post-fix (preflight refuses before any mutation, edit survives, repo byte-identical).
Add a `--resume` variant (US1 AC4). Mark `@pytest.mark.regression`, reference #4752.

### T014 — Red-first #4753 (`tests/integration/test_merge_lane_worktree_safety.py`)
Seed a lane worktree with an uncommitted tracked edit + an untracked file; assert
RED pre-fix (worktree force-removed, files gone, exit 0), GREEN post-fix (preflight
refuses fail-closed / retains under retention; files survive). Add a coord-triple
variant (dirty coord worktree → coupled teardown held back). `@pytest.mark.regression`,
reference #4753.

## Branch Strategy

Planning base: `fix/merge-destructive-op-safety`. Final merge target: `main`.
Enter the lane workspace `spec-kitty implement WP03` prepares.

## Test Strategy (ATDD)

Commit T013 + T014 FIRST as the red-first contract (RED on the lane base), then
implement T010–T012 to green. Targeted:
`.venv/bin/python -m pytest tests/integration/test_merge_primary_checkout_safety.py tests/integration/test_merge_lane_worktree_safety.py -q`
plus `tests/merge/` for the touched executor/preflight surface.

## Definition of Done

- Preflight refuses off-target/dirty primary checkout AND dirty lane/coord
  worktrees BEFORE any ref advance; `--resume` identical.
- Cleanup routes through the guarded chokepoint; clean path unchanged.
- Both red-first repros pass green (were red on base); parity tests for the
  clean/on-target/resume path pass (NFR-002).
- `ruff`/`mypy` clean; complexity ≤15; no suppressions.

## Risks

- **Ownership overlap on `executor.py`** — this WP is the sole owner of the merge/
  surface; WP02 owns only the vcs/coordination/orchestrator seams. Do not edit
  those here.
- **Residue false-positive** blocking a legitimate merge — the injected classifier
  (via WP01) prevents it; assert a residue-only `meta.json` still merges.
- **`--resume` divergence** — cover it explicitly (T013).

## Reviewer Guidance

Verify: the guard fires in preflight (before ref advance), proven by a spy/ordering
assertion (NFR-001); both repros are genuinely red on the lane base; cleanup uses
`remove_workspace` not a raw force-remove; no new dirty predicate added.
