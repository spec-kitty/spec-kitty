# Tracer — Approach

Mission: Merge/Git Destructive-Operation Safety (#4752, #4753, #4754)

## Seed (planning)

- **Strategy:** unify one *refuse-before-destroy* guard rather than patch 3 sites
  (Decision `guard_strategy`). Grounding squad found ~9 forked dirty-check
  predicates, no canonical owner — a file-lock-authority-gap-shaped defect.
- **Reuse, don't reinvent:** `git/ref_advance._dirty_entries` (residue-aware dirty
  check) + a new `RefAdvance`-style typed refusal; `merge/preflight._enforce_planning_artifact_target_branch`
  (on-target assertion) wired into the lane path; worktree removal routed through
  `core/vcs/git.py remove_workspace`.
- **Sequencing:** tidy-first enabler (the shared guard primitive) → then the three
  fixes consume it → then fold the two coupled surfaces (coord teardown,
  orchestrator-api mirror).
- **ATDD:** each issue gets a red-first `@regression` repro through the pre-existing
  entry point, modeled on `tests/integration/test_merge_lane_planning_data_loss.py`
  Layer 2 (`_real_merge_external_mocks`), before its fix.

## Appended during implement

_(to be filled per WP)_
