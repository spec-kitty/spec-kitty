---
affected_files: []
cycle_number: 2
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-29T08:44:18Z'
reviewer_agent: claude
wp_id: WP09
---

# WP09 review: cycle 2, changes requested

Reviewed: every WP09 commit from 1ce73bcca to e8806480a, on top of b3dc01fff. HEAD is 9f51bd2c4.

## Verified as fixed

**Issue 1 (documentation wiring).**
- Both helpers now take `owned=`, forward it to `commit_for_mission`, and resolve protection from `owned.repository_root`.
- The new documentation acceptance file covers the cases with and without a stale copy.
- Red-first holds: at 1ce73bcca, 1 failed and 1 passed. The row with a stale copy was already green on the base, which matches my cycle-1 probe.

**Issue 2 (T045 step 5).** Done:
- the in-progress `owned_checkout` workspace_kind row;
- the lane-mismatch row;
- owned-arm seam tests for `resolve_workspace_for_wp`, `check_doing_wps_for_staleness` and `_st_status_read_dir`.

**Issue 3, the two out-of-map fixes.**
- `lifecycle_events.py`: the new `repo_root` parameter is additive and defaults to `None`, so the resolution path is unchanged when it is not passed. The owned caller passes the fact's root (`owned.repository_root`), so this does not create a competing resolution path.
- `commit_router.py`: a one-line change to `owned.topology`. Minimal and correct.
- Both are declared in their commit bodies.
- Red-first holds: 050f21dac had 1 failed, and 9b4bbef73 had 1 failed.

**Issue 5 (T049).** Each row now asserts all of the following:
- a clean `SystemExit`;
- the registry code;
- an unchanged R snapshot and an unchanged P snapshot;
- unchanged worktree and branch lists.

The mutation test now covers all 5 commands.

**Issue 6 (T044).**
- The vacuous snapshot comparison is fixed.
- Stale-copy rows are added for O1 and O2, both flagless and flagged.
- Setup-plan FR-007 is covered in JSON (with and without a stale copy) and in human mode.
- `owned_handle` and `owned_cwd` are used.
- NFR-002 is covered by owned setup-plan (count 1) and non-owned (count 0).
- Control (a) now compares the payload shape.
- `HEAD~1 == head_before` is asserted.
- The non-substantive-spec and scaffold-only rows are present.

**Issues 7–10.**
- The campsite tests are present.
- The literal `OWNED_ACTION_UNSUPPORTED` is replaced by the enum.
- The trailing comma in `move_task` is restored (tasks.py format drift is back to 84).
- The Activity Log records the count corrections.

**Gates.**
- mypy `--strict` over 12 files gives 2 errors at both b3dc01fff and HEAD. Both are at `lifecycle_events.py:302-303` and existed before this cycle, so there are 0 new errors.
- ruff check is clean.
- Every touched function is at complexity ≤ 11.

## Issues (all must be fixed)

**Issue A [HIGH] The issue-4 fix regresses #4677 in lane and coordination worktrees.**

Location: `tasks_status_cmd.py`, the new `_tasks.get_status_read_root(st.cwd) == repo_root` guard.

I built the same repository (one active mission, a lane worktree and a `-coord` worktree) and ran bare `agent tasks status --json` from each place:

| Run from | b3dc01fff | HEAD |
|---|---|---|
| R | exit 0, default mission | exit 0, default mission |
| lane worktree | exit 0, default mission | exit 1, `mission_required` |
| coordination worktree | exit 0, default mission | exit 1, `mission_required` |

#4677's contract is that the bare command works whenever exactly one mission is active. Its tests only exercise cwd = R, but the behaviour in worktrees was real, and agents run `status` from lane worktrees.

Required fix:
- Narrow the exclusion to owned checkouts only. Skip the sole-active default only when the invoking checkout carries an ownership claim (for example, it resolves to a linked checkout that is not a lane or coordination worktree of R). Do not skip it whenever cwd is anything other than R.
- Add tests:
  - bare `status` from a lane worktree defaults to the sole mission;
  - bare `status` from a coordination worktree defaults to the sole mission;
  - bare `status` from owned P, while R holds an unrelated sole mission, never renders R's mission.
- Tighten `test_issue4_flagless_status_from_p_without_mission_never_shows_r_unrelated_mission`. It currently passes on either outcome; it should assert the specific refusal.

**Issue B [HIGH] The fix for the lifecycle residue is incomplete, and the raising pins do not pin `get_main_repo_root`.**

Location: `mission_setup_plan.py:714`, in `_commit_plan_if_substantive`.

`emit_artifact_phase(PLAN_COMPLETED)` is still called without `repo_root=`. On an owned run it walks `_repo_root_for_lifecycle_log` → `resolve_canonical_root` → `get_main_repo_root`. I confirmed this at HEAD with a probe that arms a raising `get_main_repo_root` once `resolve_owned_or_adopt` has minted the fact:
- the probe passes for owned `status` (cwd R and cwd P);
- it fails for owned `setup-plan` at exactly this call.

Mutation check of the two pins that "passed first time". I injected a `get_main_repo_root(...)` call on each owned arm:
- **Status arm** (`_st_resolve_owned`), pin 5c5194f6b: it went red only because a unit fixture that is not a git repository returned the wrong value. In a real repository, `get_main_repo_root(P) == R`, so the mutant survives. None of the 34 owned status acceptance rows went red.
- **Setup-plan arm** (`_resolve_setup_plan_scope`), pin 84b28876e: it stayed green. Only `test_resolve_setup_plan_scope_owned_arm_uses_the_fact` went red, again only by comparing values in a non-repository fixture.

So neither pin covers `get_main_repo_root`.

Required fixes:
1. Pass `repo_root=owned.repository_root` into the PLAN_COMPLETED emission. Thread `owned` into `_commit_plan_if_substantive`, which already receives it.
2. In both end-to-end pins (the real owned `status` run and the real owned `setup-plan` run), arm a raising `get_main_repo_root` after minting. Wrap `_owned_checkout.resolve_owned_or_adopt` so the pin raises only once the fact exists, because the minter legitimately calls `get_main_repo_root`. Patch every module alias of the function, not just `specify_cli.core.paths`.
3. Show red-first for the PLAN_COMPLETED fix: the armed pin must fail on the current HEAD before the fix lands.

## Low

- `test_tasks_status_cmd_seam.py`: cycle 2 adds 4 new lines of format drift (34 → 38 against b3dc01fff), which contradicts the Activity Log's "drift only in pre-existing hunks". Run `ruff format` on the new hunks only.

## Note

In one parallel run (`-n 8`) alongside 27 other files, `tests/architectural/test_status_module_boundary.py::test_ast_scan_no_direct_status_imports_repo_wide` failed once. It passes on its own at HEAD (6/6) and at b3dc01fff. This looks like an interaction between files run in parallel, not WP09's diff. It is recorded here and not attributed to WP09.
