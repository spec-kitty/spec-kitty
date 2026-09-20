---
work_package_id: WP01
title: Refuse-before-destroy guard primitive + typed refusal
dependencies: []
requirement_refs:
- C-001
- C-002
- C-005
- FR-007
- NFR-003
- NFR-005
planning_base_branch: fix/merge-destructive-op-safety
merge_target_branch: fix/merge-destructive-op-safety
branch_strategy: Planning artifacts for this mission were generated on fix/merge-destructive-op-safety. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/merge-destructive-op-safety unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Implementation
history:
- at: '2026-09-19T21:10:00Z'
  actor: system
  action: Prompt generated for merge-destructive-op-safety mission
agent_profile: python-pedro
authoritative_surface: src/specify_cli/git/
create_intent:
- src/specify_cli/git/destructive_guard.py
- tests/specify_cli/git/test_destructive_guard.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/git/destructive_guard.py
- tests/specify_cli/git/test_destructive_guard.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '4752'
- '4753'
---

# Work Package Prompt: WP01 – Refuse-before-destroy guard primitive

## ⚡ Do This First: Load Agent Profile

Load the `python-pedro` profile (role: implementer) via the profile-load skill
(`/ad-hoc-profile-load` or `spec-kitty charter context`) before reading anything
else. Then read `spec.md`, `plan.md`, `data-model.md`, and
`contracts/guard-api.md` in this mission's feature dir.

## Objective

Create ONE shared, git-plumbing-pure *refuse-before-destroy* guard that the three
fix WPs consume. This is the tidy-first enabler: it closes the data-loss class by
construction instead of forking a 10th dirty-check predicate (the grounding squad
found ~9 already). It must reuse the residue-aware `_dirty_entries` predicate and
raise a NEW typed refusal — never overload `SafeCommitHeadMismatch`.

## Context (grounding — cite when in doubt)

- Gold-standard existing guard: `src/specify_cli/git/ref_advance.py`
  — `_dirty_entries` (`:240`, residue-aware, `--ignored`, tree-obstruction,
  meta-lock exemption, injectable `is_residue`) and `RefAdvanceDirtyWorktreeError`
  (`:82`, error_code + resume remediation) are the patterns to mirror.
- On-target assertion to reuse: `src/specify_cli/merge/preflight.py`
  `_enforce_planning_artifact_target_branch` (`:205`, `git rev-parse --abbrev-ref HEAD`).
- Do NOT reuse `SafeCommitHeadMismatch` (`git/commit_helpers.py:138`) — it has ≥6
  downstream catchers whose semantics must not change (C-002).
- git-plumbing purity: no `specify_cli` import in `git/`; the churn classifier
  (`coordination.coherence.is_toolchain_generated_churn`) is INJECTED by the caller
  (C-005).

## Subtasks

### T001 — `DestructiveOpRefused` typed refusal
Define an exception with: `error_code` (`MERGE_UNSAFE_PRIMARY_OFF_TARGET` |
`MERGE_UNSAFE_PRIMARY_DIRTY` | `MERGE_UNSAFE_WORKTREE_DIRTY`), `worktree_path`,
`current_branch`, `expected_branch`, `dirty_entries: list[str]`, `remediation: str`.
Message must name the condition and the fix (incl. the `--resume` note). Model on
`RefAdvanceDirtyWorktreeError`.

### T002 — `assert_checkout_on_target(repo_root, expected_branch, *, env=None)`
Raise `DestructiveOpRefused(MERGE_UNSAFE_PRIMARY_OFF_TARGET)` when
`git rev-parse --abbrev-ref HEAD != expected_branch`. Reuse the rev-parse logic
from `_enforce_planning_artifact_target_branch` — extract a shared helper rather
than duplicating (DRY; C-001). No side effects.

### T003 — `assert_worktree_clean(...)` + `guarded_worktree_remove(...)` (the shared removal seam)
(a) `assert_worktree_clean(worktree, *, new_sha=None, is_residue, env=None)` —
delegate to `ref_advance._dirty_entries(...)` with the injected `is_residue`
classifier; raise `DestructiveOpRefused(MERGE_UNSAFE_WORKTREE_DIRTY)` carrying the
dirty entries when the list is non-empty. `is_residue` is a required keyword — the
caller injects it; the module must not import `coordination.*` itself (C-005).
(b) `guarded_worktree_remove(worktree, *, retain, is_residue, env=None)` — the
**shared removal chokepoint** the fix WPs route through (NOT the dead
`core/vcs/git.py remove_workspace`, which has zero production callers — brownfield
scout). It runs `assert_worktree_clean` unless `retain` is True; on a clean (or
retained-and-kept) worktree it performs the inline `git worktree remove --force`;
when `retain` and dirty, it KEEPS the worktree (no removal) and reports it. Returns
a small result (removed | retained-dirty). This is the single authority every live
destroy site calls.

### T004 — Unit tests (`tests/specify_cli/git/test_destructive_guard.py`)
Cover: on-target passes / off-target raises; clean passes / tracked-dirty raises;
untracked-obstruction raises; **residue fixture** — a `meta.json` whose only diff
is the VCS-lock stamp passes (NFR-003, use a stub `is_residue` matching the real
classifier's contract). Assert the raised `error_code` + `dirty_entries`.

### T005 — Purity + complexity
Confirm no `specify_cli`/`coordination` import in the new module (git-plumbing
purity); keep each function ≤15 cyclomatic complexity; run `ruff check` +
`ruff format` + `mypy` on the new files (zero issues, no suppressions).

## Branch Strategy

Planning base: `fix/merge-destructive-op-safety`. Final merge target: `main`.
Execution worktrees are allocated per computed lane from `lanes.json` — enter the
resolved workspace `spec-kitty implement WP01` prepares; do not reconstruct paths.

## Test Strategy (ATDD)

This WP is pure new surface, so its unit tests ARE the red-first contract: write
T004 first (red — module/functions absent), then implement T001–T003 to green.
Targeted run: `.venv/bin/python -m pytest tests/specify_cli/git/test_destructive_guard.py -q`.

## Definition of Done

- New module + typed refusal + two assert functions + `guarded_worktree_remove`
  (the shared removal seam) exist and are importable.
- All T004 unit tests pass, including the residue-exempt case and a
  `guarded_worktree_remove` retain-keeps-dirty / clean-removes case.
- No `specify_cli`/`coordination` import in `git/destructive_guard.py`.
- `ruff`/`mypy` clean; complexity ≤15; no suppressions.
- `contracts/guard-api.md` signatures honored (this is the frozen shared contract).

## Risks

- **False-positive over-block** if the residue classifier is not honored — pin it
  in T004 (NFR-003).
- **Signature drift** breaks WP02–WP04 — freeze the API per `contracts/guard-api.md`.

## Reviewer Guidance

Verify: no `SafeCommitHeadMismatch` reuse; `_dirty_entries` delegation (not a new
porcelain parse); injected `is_residue` (no `coordination` import); residue test
present and meaningful; error codes match the data model.
