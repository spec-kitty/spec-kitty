---
affected_files: []
cycle_number: 1
mission_slug: regression-slice-cleanup-01M42WCF
reproduction_command:
reviewed_at: '2026-10-04T08:21:36Z'
reviewer_agent: claude
wp_id: WP02
---

# WP02 review feedback (cycle 1) - reviewer-renata

**Issue 1 (blocking): `#5100 A3` "a refused implement leaves no tracked-file changes" lost its last guard.**
`test_dirty_checkout_refused_but_resume_allowed` was removed, but its Half-A assertion
`_git(repo_a, "status", "--porcelain", "--untracked-files=no") == ""` is the only pin on the
refusal-before-VCS-lock ordering in `src/specify_cli/cli/commands/implement.py` (~L2164-2168, the
comment "#5100 A3: refusals ... run BEFORE the VCS lock is written into meta.json").
Planted break (reviewer, reverted, `git status --short src/` empty): swap the two lines so
`_ensure_vcs_in_meta(...)` runs before `_refuse_repo_root_checkout_if_unavailable(...)`.
- `tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py` + trimmed
  `tests/integration/test_single_branch_write_checkout_e2e.py`: 20 passed (GREEN).
- Removed test (from base): 1 failed - `assert 'M kitty-spec...ZJA/meta.json' == ''` (RED).
Per the planted-break protocol a green guard flips the verdict to KEEP.
Fix (either):
  (a) preferred, cheaper: add a test in `tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py`
      (its `repo` fixture drives the real `implement()`) that runs a dirty-checkout refusal on a
      mission whose `meta.json` has no `vcs` key and asserts `git status --porcelain --untracked-files=no`
      is empty / `meta.json` unchanged; re-plant the swap above and record RED; or
  (b) restore the Half-A part of `test_dirty_checkout_refused_but_resume_allowed` in the e2e file
      (Half B / resume exemption is covered by `test_resuming_the_already_in_progress_wp_is_exempt_from_occupancy_and_dirty`).
Land the new guard in a commit before (or with) any further trim, and record the planted-break row.

**Nit 1:** `tests/integration/test_single_branch_write_checkout_e2e.py` `_assert_setup_ok` docstring
still says "this file's own red-first acceptance assertions"; #5100 is fixed - reword (e.g. "acceptance assertions").

**Adjudicated, not blocking:**
- Flagged loss (b) commit_to_target CLI chain on main: reviewer planted `resolve_for_mission` -> `resolve(repo_root)`
  at `implement.py:118` and `tasks_shared.py:386`; `tests/git/test_protection_policy_mission_scope.py` goes RED
  (2 call-site params) alongside the removed test - covered by a cheaper guard. OK to remove.
- Flagged loss (c) finalize wiring guarded only by `test_specify_topology_flag.py` (slow): acceptable.
- Protected mint + implement-on-mission-branch: covered by `tests/core/test_mission_create_protected_single_branch.py` (W1 test).

**Verified OK:** src/ diff empty; P-5620-4 re-planted (both arms -> `except KeyError`): units 4/4 + smoke RED;
P-5620-5 re-planted (dirty check off): refusals file 2 failed; new unit file non-vacuous, stubs only the
raising collaborators, all < 1 s; trio unmark keeps module `unit` marker; ruff/format/mypy clean; marker gates 8 passed;
touched files 82 passed; `-m regression` collects 0 in touched files; commit messages conventional with the
required trailer and no model names.
