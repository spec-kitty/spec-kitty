---
affected_files: []
cycle_number: 3
mission_slug: owned-checkout-lifecycle-authority-01M3M2ZB
reproduction_command:
reviewed_at: '2026-09-29T09:11:31Z'
reviewer_agent: claude
wp_id: WP09
---

# WP09 review: cycle 3, changes requested

Reviewed commits: f21ce93e3, e4b3fd1b1, 0bca59bfd and d04a238a0, on top of 9f51bd2c4.

## Verified as fixed

**Cycle-2 item 2 (PLAN_COMPLETED).**
- `_commit_plan_if_substantive` now passes `repo_root=owned.repository_root` to `emit_artifact_phase`.
- The armed pins wrap `resolve_owned_or_adopt`, patch every module alias of `get_main_repo_root`, and record hits so that swallowed exceptions still count. They are non-vacuous. I injected three mutations at d04a238a0 and each one turns the armed pins red:
  - M1: status owned arm calls `get_main_repo_root` → 2 failed;
  - M2: setup-plan owned arm calls `get_main_repo_root` → 1 failed;
  - M3: PLAN_COMPLETED fix reverted → 1 failed.
- Red-first holds: at f21ce93e3, `test_armed_get_main_repo_root_pin_setup_plan` fails and the two status rows pass.

**Cycle-2 item 1, as far as the lane and coordination worktrees go.**
- At 0bca59bfd the lane and coordination rows are red; at d04a238a0 they are green.
- The cycle-2 format drift in `test_tasks_status_cmd_seam.py` is back to baseline.

## Issue (must fix)

**Issue A [HIGH] `tasks_status_cmd.py` `_st_is_owned_candidate_checkout` is a parallel ownership predicate that disagrees with WP08/WP02 adoption and still regresses #4677.**

I built one repository: R holds one active mission with `lanes.json` listing lane-a. I then ran bare `agent tasks status --json` from each checkout below.

| Invoking checkout | b3dc01fff (before) | d04a238a0 | What adoption says (`adopt_owned_checkout`) |
|---|---|---|---|
| R | default | default | n/a |
| lane worktree listed in lanes.json | default | default | not owned |
| **stale lane worktree** under `.worktrees`, not in lanes.json | default | **mission_required** | not owned (the branch does not match, so the minter refuses) |
| coordination worktree | default | default | not owned |
| **plain linked checkout of R** (`git worktree add ../hotfix`), no claim, holding only R's own mission content | default | **mission_required** | not owned |
| owned P outside R | default (the cycle-1 leak) | mission_required | owned |
| owned P under `R/.worktrees` | default (leak) | mission_required | owned |

The owned rows are now right. The two rows in bold are new regressions of #4677, because nothing there is owned.

The cause is that the helper re-composes a topology heuristic, instead of asking the canonical authority whether this checkout owns a mission. It rebuilds:
- `get_status_read_root`;
- `classify_worktree_topology`;
- `read_lanes_json`;
- `predict_lane_worktree`.

Those are the same pieces `core/owned_mission.py` already owns as `_candidate_checkout_root`, `_is_coordination_worktree`, `_is_lane_worktree_of_mission` and adoption itself. This breaks the single-authority rule: there is now a second "is this checkout owned?" predicate, and it already disagrees with the first.

Required fix:
- Key the skip on WP08/WP02's adoption semantics, not on topology. Skip the #4677 default only when the invoking checkout genuinely owns a mission. That means `adopt_owned_checkout(R, cwd, <the toplevel's own sole active mission>)`, or an equivalent public predicate exported from `core/owned_mission.py`, returns a fact. It must be one authority, reused by both adoption and this guard. A small public wrapper in `owned_mission.py` is an acceptable declared out-of-map edit.
- Delete `_st_is_owned_candidate_checkout`'s own classification logic. Remove its compat-surface registration if the symbol goes away.
- Keep failing toward #4677 when the registry is unavailable.
- Tests are needed for these rows:
  - the stale lane worktree gets the default;
  - the plain linked checkout gets the default;
  - owned P outside R is refused;
  - owned P under `R/.worktrees` is refused;
  - the existing listed-lane, coordination and R rows stay green.
- Show red-first for the two regressed rows.

## Gates (at d04a238a0)

- Targeted tests: 907 passed (17 files, listed in the handback).
- ruff check is clean. Every function in `tasks_status_cmd.py` has complexity ≤ 11.
- mypy `--strict` over 7 files: only the 2 pre-existing errors at `lifecycle_events.py:302-303`.

## Out of scope

The `emit_artifact_phase` sites in `mission_finalize.py` and `mission_creation.py` are routed to WP13, per the orchestrator. They do not block WP09.
