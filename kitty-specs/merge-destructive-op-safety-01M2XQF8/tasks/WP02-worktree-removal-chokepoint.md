---
work_package_id: WP02
title: Route coord + orchestrator worktree destroys through the guarded seam
dependencies:
- WP01
requirement_refs:
- C-003
- C-006
- FR-003
- FR-004
- FR-006
- NFR-001
planning_base_branch: fix/merge-destructive-op-safety
merge_target_branch: fix/merge-destructive-op-safety
branch_strategy: Planning artifacts for this mission were generated on fix/merge-destructive-op-safety. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/merge-destructive-op-safety unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-merge-destructive-op-safety-01M2XQF8
base_commit: 0a3ad9b1026021de6b537beca82563fe0fed3a8d
created_at: '2026-09-19T22:15:56.183539+00:00'
subtasks:
- T006
- T007
- T008
- T009
phase: Phase 1 - Implementation
history:
- at: '2026-09-19T21:10:00Z'
  actor: system
  action: Prompt generated for merge-destructive-op-safety mission
agent_profile: python-pedro
authoritative_surface: src/specify_cli/coordination/
create_intent:
- tests/coordination/test_coord_teardown_guard.py
- tests/orchestrator_api/test_worktree_cleanup_guard.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/coordination/workspace.py
- src/specify_cli/orchestrator_api/commands.py
- tests/coordination/test_coord_teardown_guard.py
- tests/orchestrator_api/test_worktree_cleanup_guard.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '4753'
---

# Work Package Prompt: WP02 – Worktree-removal chokepoint + coupled folds

## ⚡ Do This First: Load Agent Profile

Load the `python-pedro` profile (role: implementer) via the profile-load skill
before anything else. Then read `spec.md`, `plan.md`, `data-model.md`,
`contracts/guard-api.md`, and `contracts/routing-invariant.md`.

## Objective

Route the LIVE user-facing worktree destroys on the coordination and
orchestrator-api paths through WP01's shared `guarded_worktree_remove` seam, so a
dirty user worktree is never `--force`-removed absent explicit retention.

**Corrected scope (brownfield scout):** `core/vcs/git.py remove_workspace` is a
DEAD adapter (zero production callers) and is NOT on any destroy path — do not
touch it. The real destroys are inline `git worktree remove --force` calls; this
WP owns the coordination + orchestrator ones. (The executor lane-cleanup destroy
is WP03's.) The scratch workspace stays unconditional (C-006).

## Context (grounding — verify at current line before editing)

- `src/specify_cli/coordination/workspace.py` — TWO force-remove sites:
  `teardown` (~`:300`) AND `_remove_worktree_registration` (~`:186`, a
  stale-registration prune called from teardown and elsewhere). Route BOTH through
  the guarded seam; the stale-prune (path already absent) is guard-EXEMPT but must
  be routed-and-explicitly-exempted, not left as a raw `--force`.
- Coord-triple coupling is ALREADY grouped atomically in the EXECUTOR
  (`merge/executor.py` `_teardown_coordination_triple`, worktree-first → branch →
  marker) — `coordination/workspace.py teardown` owns ONLY the worktree leg by
  design (it must NOT delete the branch). So a guard refusal at the coord-worktree
  step naturally propagates and holds the branch+marker back (FR-004) — preserve
  that; do not add branch deletion here.
- `src/specify_cli/orchestrator_api/commands.py` (~`:869`) — a live
  `git worktree remove --force` gated by `remove_worktree` (~`:840`). Route it
  through the guarded seam (this is the orchestrator mirror a patch-N would miss).
- Scratch workspace (`merge/workspace.py cleanup_merge_workspace`) is OUT of scope
  (C-006). Guard uses WP01 `guarded_worktree_remove(..., retain, is_residue=<injected>)`
  with `coordination.coherence.is_toolchain_generated_churn`.

## Subtasks

### T006 — Route coord teardown through the guarded seam
Replace `coordination/workspace.teardown`'s inline `git worktree remove --force`
(~`:300`) with a call to WP01 `guarded_worktree_remove(..., retain=False)` (these
teardown paths only run when removal is already requested; do NOT wire the
operator's `--keep-worktree`/`retain_worktrees` into the guard's `retain` — review
ADVISORY-3 — that flag already skips teardown upstream).
Preserve today's behavior for a clean coord worktree; on dirt (no retention) the
raised `DestructiveOpRefused` propagates so the executor's triple holds branch +
marker back atomically (FR-004).

### T007 — Route the stale-registration prune (explicit exemption)
Route `_remove_worktree_registration` (~`:186`) through the same seam with an
explicit guard-exemption (the registration's worktree path is already absent /
prunable, so there is no user work to lose). No raw `--force` may remain in
`coordination/workspace.py`.

### T008 — Route orchestrator-api destroy
Replace the inline `git worktree remove --force` at
`orchestrator_api/commands.py` (~`:869`) with `guarded_worktree_remove(...,
retain=False)`, enforcing the identical rule on the orchestrator
path.

### T009 — Tests
`tests/coordination/test_coord_teardown_guard.py`: dirty coord worktree → the
guarded seam refuses; assert the coord branch + marker survive with it (triple
held atomically); clean coord worktree → removed as today; retention → kept.
`tests/orchestrator_api/test_worktree_cleanup_guard.py`: dirty orchestrator
worktree → refuse (default path); clean → removed; retention → kept. Each red-first
test must exercise the DEFAULT (non-retaining) call so the pre-fix red is a
missing-refusal, not a signature error.

## Branch Strategy

Planning base: `fix/merge-destructive-op-safety`. Final merge target: `main`.
Enter the lane workspace `spec-kitty implement WP02` prepares.

## Test Strategy (ATDD)

Write T009 first (red — chokepoint currently force-removes dirty worktrees), then
implement T006–T008 to green. Targeted:
`.venv/bin/python -m pytest tests/git_ops/test_remove_workspace_guard.py tests/coordination/test_coord_teardown_guard.py -q`.

## Definition of Done

- No raw `git worktree remove --force` remains in `coordination/workspace.py` or
  the orchestrator destroy at `orchestrator_api/commands.py` — all route through
  WP01 `guarded_worktree_remove`.
- Dirty coord/orchestrator worktrees are refused (or retained under retention);
  clean ones removed as today.
- Coord-triple retention is atomic on refusal (FR-004 test passes: branch + marker
  survive with the worktree).
- The stale-registration prune is routed with an explicit guard-exemption.
- `ruff`/`mypy` clean; complexity ≤15; no suppressions.

## Risks

- **Half-torn coord triple** if T007 guards only the worktree — the coupling test
  is the guard against that.
- **Breaking scratch cleanup** — keep C-006 path unconditional; do not route the
  scratch workspace through the dirty check.

## Reviewer Guidance

Verify: one guarded chokepoint (not three bespoke checks); coord triple coupling;
scratch workspace still unconditional; retention path preserves work without a
false success line (FR-006).
