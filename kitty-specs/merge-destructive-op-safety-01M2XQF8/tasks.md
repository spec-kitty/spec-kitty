# Tasks: Merge/Git Destructive-Operation Safety

**Mission**: merge-destructive-op-safety-01M2XQF8 | **Issues**: #4752, #4753, #4754
**Planning base**: `fix/merge-destructive-op-safety` | **Final merge target**: `main`

Completion is event-sourced — record subtask progress with
`spec-kitty agent tasks mark-status Txxx --status done`, not markdown checkboxes.

## Subtask Index (reference only)

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | `DestructiveOpRefused` typed refusal (error_code, paths, dirty_entries, remediation) | WP01 | |
| T002 | `assert_checkout_on_target(repo_root, expected_branch)` (reuse rev-parse logic) | WP01 | |
| T003 | `assert_worktree_clean(worktree, *, new_sha, is_residue)` delegating to `_dirty_entries` | WP01 | |
| T004 | Guard unit tests incl. `meta.json` VCS-lock residue fixture (NFR-003) | WP01 | |
| T005 | git-plumbing purity + complexity ≤15 verification | WP01 | |
| T006 | Retain-aware dirty guard in `core/vcs/git.py remove_workspace` | WP02 | |
| T007 | Route `coordination/workspace.teardown` through the guard; couple coord triple (FR-004) | WP02 | |
| T008 | Route `orchestrator_api/commands` cleanup mirror through the guard | WP02 | |
| T009 | Chokepoint tests: dirty-refuse / retain-keeps / clean-removes / coord-triple-atomic | WP02 | |
| T010 | Pre-mutation merge safety preflight (primary + all lane/coord worktrees) before ref advance | WP03 | |
| T011 | Guard `_refresh_primary_checkout_after_merge` (no reset when off-target) | WP03 | |
| T012 | Route executor cleanup loop through the WP02-guarded `remove_workspace` | WP03 | |
| T013 | Red-first `test_merge_primary_checkout_safety.py` (#4752) incl. `--resume` | WP03 | |
| T014 | Red-first `test_merge_lane_worktree_safety.py` (#4753) incl. coord-triple | WP03 | |
| T015 | Gate `abort_git_merge` on active spec-kitty state; scope to merge workspace | WP04 | [P] |
| T016 | Fix `_dispatch_abort` contradictory success line | WP04 | [P] |
| T017 | Red-first `test_merge_abort_scope.py` (#4754) | WP04 | [P] |
| T018 | Architectural routing gate: destructive commands only behind guard/chokepoint | WP05 | |
| T019 | No-new-parallel-dirty-predicate assertion | WP05 | |
| T020 | Self-mutation companion test (route-around → gate RED) | WP05 | |

## Work Packages

### WP01 — Refuse-before-destroy guard primitive (enabler)
- **Goal**: One shared, git-plumbing-pure guard primitive + typed refusal, reusing the residue-aware dirty check.
- **Priority**: P0 (foundation) · **Depends on**: —
- **Independent test**: unit tests prove on/off-target + clean/dirty + residue-exempt behavior in isolation.
- **Subtasks**: T001 T002 T003 T004 T005
- **Est.**: ~250 lines

### WP02 — Worktree-removal chokepoint + coupled folds
- **Goal**: Guard `remove_workspace`; route coord teardown + orchestrator-api mirror through it; couple the coord triple.
- **Priority**: P0 · **Depends on**: WP01
- **Independent test**: chokepoint refuses dirty removal, retains under retention, removes when clean, coord-triple atomic.
- **Subtasks**: T006 T007 T008 T009
- **Est.**: ~300 lines

### WP03 — Merge pre-mutation preflight + executor routing (#4752, #4753)
- **Goal**: Detect all unsafe worktrees BEFORE ref advance; guard the primary reset; route cleanup through the chokepoint.
- **Priority**: P0 · **Depends on**: WP01, WP02
- **Independent test**: red-first repros for #4752 and #4753 (incl. `--resume` + coord-triple) go red→green.
- **Subtasks**: T010 T011 T012 T013 T014
- **Est.**: ~380 lines

### WP04 — `merge --abort` scoping (#4754)
- **Goal**: Only abort a git merge when active spec-kitty merge state exists; never touch the user's `repo_root` merge.
- **Priority**: P1 · **Depends on**: — (parallel)
- **Independent test**: red-first repro for #4754 (user MERGE_HEAD, no spec-kitty state) goes red→green.
- **Subtasks**: T015 T016 T017
- **Est.**: ~200 lines

### WP05 — Unification routing gate (NFR-006)
- **Goal**: Non-vacuous architectural gate proving the defect class is closed by construction.
- **Priority**: P1 · **Depends on**: WP02, WP03, WP04
- **Independent test**: gate is green on the routed tree and RED under a deliberate route-around (self-mutation).
- **Subtasks**: T018 T019 T020
- **Est.**: ~200 lines

## Dependency Graph

```
WP01 ──┬── WP02 ── WP03 ──┐
       └───────────────────┼── WP05
WP04 ───────────────────────┘
```

## MVP

WP01 + WP03 close the two P0 data-loss reproductions (#4752, #4753) once WP02's
chokepoint exists; WP04 closes the P1 (#4754); WP05 locks the class shut.
