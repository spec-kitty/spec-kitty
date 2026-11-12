---
affected_files: []
cycle_number: 1
mission_slug: settled-placement-surface-01M78GR4
reproduction_command:
reviewed_at: '2026-11-12T19:38:51Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP01
---

# WP01 review feedback (cycle 1) -- reviewer-renata

**There is no code finding. The verdict on the code is APPROVE.**

This return to `planned` exists only so the implementer can re-claim WP01 with its real profile
recorded. The claim was made with `--agent claude` and no `--profile`, so the implementer was
recorded as `claude::`, and the approval was refused with `SINGLE_BRANCH_REVIEW_NOT_INDEPENDENT`.
Re-claim with `--profile python-pedro`, move to `for_review` with no code change, and the review
will be approved.

## Evidence
- The red commit 467f0cb9 fails on the pre-fix tree (Test A: `surface_root` was `repo`, not the
  coordination worktree) and passes on HEAD.
- Targeted tests: 3049 passed, 5 skipped.
- Architectural gate files (7 named files): 236 passed.
- ruff, ruff format and mypy are clean on the changed files. Complexity is 15 or below.
- Invariants hold:
  - `path` is unchanged.
  - The owned arm is unchanged.
  - No topology is read.
  - No new `mission_runtime -> specify_cli` import.
  - The kernel primitive is built on `find_ancestor`.
- Lane-path change of `primary_partition_checkout`:
  - Every production caller passes the main repo root (`find_repo_root` / `locate_project_root`
    / `get_main_repo_root`).
  - So behaviour is unchanged for Missions that have not settled.

## Non-blocking findings (optional; none are required for approval)
1. (low) `tests/specify_cli/coordination/test_planning_commit.py`:
   `test_primary_dir_outside_any_checkout_has_no_holder` now uses the same stub as
   `test_primary_dir_in_the_root_checkout_has_no_holder`, so it duplicates that case.
   The fallback is covered by `test_containing_checkout_falls_back_to_the_main_repo_root_outside_every_checkout`.
2. (low) `tests/mission_runtime/test_write_dir_settled_surface_root.py:43`:
   - The `is_relative_to` assertion also passes on the old code, because the coordination
     worktree sits under `repo/.worktrees/`.
   - The equality assertion at line 44 is the one that fails red.
3. (nit) `src/kernel/git_anchor.py` `checkout_root_containing`:
   - The docstring says the result is always resolved.
   - `find_ancestor` returns unresolved candidates when the start path cannot be resolved (a
     symlink loop).
   - `_containing_checkout` already handles that case.
4. (nit) The test module re-exports the fixture through `__all__ = ["_quiet_status_fanout"]`.
   The repo's existing pattern is `# noqa: F401` with a reason.
   Either is acceptable.
