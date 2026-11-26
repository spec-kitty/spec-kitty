---
work_package_id: WP14
title: 'End-to-end route: three-lane and rollback cases'
dependencies:
- WP12
requirement_refs:
- FR-008
- FR-009
- SC-004
planning_base_branch: fix/approved-lane-resolution-route
merge_target_branch: fix/approved-lane-resolution-route
branch_strategy: Planning artifacts for this mission were generated on fix/approved-lane-resolution-route. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/approved-lane-resolution-route unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-approved-lane-resolution-route-01M7WW0Z
base_commit: 6f3123b35f5e665e2650b1b9b4f8c48e76e3cebd
created_at: '2026-11-25T22:08:45.688532+00:00'
subtasks:
- T055
- T056
- T057
- T058
phase: Phase 3 - Surfaces and proof
history:
- at: '2026-11-20T17:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/terminus/
create_intent:
- tests/terminus/test_approved_lane_resolution_route_three_lane.py
execution_mode: code_change
model: ''
owned_files:
- tests/terminus/test_approved_lane_resolution_route_three_lane.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP14 – End-to-end route: three-lane and rollback cases

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, record what you changed with `spec-kitty agent tasks add-history <WPID> --note "..."` (stored in the status event log).

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`,````bash`

---

## Objectives & Success Criteria

WP12 proved the two-lane route on the coordination topology under squash and `--strategy merge`, the controls N1 to N3, SC-003 and the residual control. This WP finishes the end-to-end proof, through the real CLI and WP12's frozen support module:

1. **SC-004 / FR-009** (T055): after a rolled-back run, the next run is not refused because of the run's own auto-rebase merge; a foreign commit made after the rollback is judged as today, never reset.
2. **Three-lane route** (T056, FR-008's three-lane variant, FR-002's exact sibling set): lane-c depends on lane-b; lane-d is an independent, non-overlapping exact-set control that is never named as a sibling. Each conflicting lane goes through one send-back and review cycle, and the Mission lands (SC-001's "one cycle per conflicting lane").
3. **Three-lane dependent stamp** (T057): lane-c's approval stamp reaching lane-b's unreviewed merge does not excuse it (the own-lane rule, R-04).
4. **Remaining matrix cells** (T058): the two-lane route on the LANES topology (no coordination branch) under squash and `--strategy merge`.

Done when all four subtasks are green through the real CLI, with no `xfail` and no `skip`, and the quality gates are clean.

This WP adds **tests only**, in one new module. It imports WP12's support module and never edits it (frozen once WP12 was approved).

**No xfail exit.** A strict `xfail` or a `skip` on any happy-path step (T055's second run, T056, T058) BLOCKS approval of this WP; it is never an approved end state. If a step fails because of a gap in the CLI, the lifecycle, the rollback or the remedy: do not patch `src/` here, and do not mark the step xfail. Stop, record the failing step with `spec-kitty agent tasks add-history WP14 --note "route gap: <step>, <exact command>, <exit code>, <output excerpt>"`, and report to the runner, who reopens the WP owning the failing surface (for example WP03 for the rollback, WP07 for the remedy or sibling naming, WP08 for `--incorporate`, WP05 for the claim refusal). If WP12's support module lacks something you need, write a local helper in your own module; if that is impossible without editing the support module, stop and report (the runner reopens WP12).

## Context & Constraints

- Read: `.kittify/charter/charter.md`; mission `spec.md` (US1, US2, US6, FR-002, FR-008, FR-009, SC-001, SC-004, Edge Cases "Three lanes"), `plan.md` IC-08, `research.md` R-03, R-04, R-05, `contracts/stale-remedy.md`, `contracts/refusal-codes.md` (including "Rollback outcome LANE_MOVED_SINCE_AUTO_REBASE"), `quickstart.md`, `tasks.md`.
- WP12's prompt and its landed support module `tests/terminus/approved_lane_route_support.py`: `build_conflicting_lanes_mission`, `add_dependent_and_control_lanes`, `run_route`, `branch_reflog_lengths`, `assert_no_branch_moved`, `consolidate_in_process`, `one_shot_gate_fail`, `cli`, `consolidate`, `printed_commands`, `resolve_conflict`, `approval_event`. Read the landed names and docstring (including the three-lane shape WP12's author recorded) before writing anything.
- **Integrity invariants** the tests pin: C-001 (no unreviewed resolution lands), C-002 (no attestation flag anywhere in the route), C-003 (the gate's unreviewed-merge rule stays), C-004 (only an unforced, independent approval restamps), C-006 (the rollback restores only inside the single rollback authority), fail closed (any refusal names a code; an exit 0 without the "Reconciliation verified" banner is a failure of the test).
- Never use `restamp_approvals_at_lane_tips`, `_restamp_approvals`, `--force` on a positive path, or the same identity for implementer and reviewer.
- Never loosen or bypass the resume lane-tip CAS (`state.lane_tip_cas_ok`) to make SC-004 pass: SC-004 is met by WP03's lane restore.
- Frozen modules, import only: `approved_lane_route_support.py`, `post_approval_support.py`, `canceled_dependency_support.py`, `mixed_lane_support.py`, `rollback_harness.py`, `conftest.py`.
- Terminology in test names and messages: Mission, consolidate, incorporate, re-review. Never "feature", never "sync".

## Branch Strategy

- **Strategy**: set by finalize-tasks
- **Planning base branch**: fix/approved-lane-resolution-route
- **Merge target branch**: fix/approved-lane-resolution-route

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Implement command: `spec-kitty agent action implement WP14 --agent claude --mission approved-lane-resolution-route-01M7WW0Z`

## Subtasks & Detailed Guidance

### Subtask T055 – SC-004: the next run after a rollback is not refused because of the run's own merge

- **Purpose**: SC-004 / FR-009 end to end through the next CLI run. WP03 proves the rollback unit; this proves the operator's next consolidate.
- **Test**: `test_next_run_after_rollback_is_not_refused_by_own_auto_rebase_merge` in `tests/terminus/test_approved_lane_resolution_route_three_lane.py`.
- **Steps**:
  1. Build two approved lanes whose overlapping edits merge **cleanly** (lane-b is stale after lane-a lands and its auto-rebase succeeds). If WP12's builder only makes the conflicting shape, build the clean variant locally in your module the same way (seed the shared file on the target, disjoint non-adjacent edits, lane worktrees allocated with `allocate_lane_worktree`, approvals through the production shell). Fixture preconditions (asserted): `git merge-tree --write-tree <lane-a> <lane-b>` exits 0; both lane worktrees exist.
  2. First run in-process with `consolidate_in_process` and `one_shot_gate_fail`: it auto-rebases lane-b, lands the lanes, then FAILs at the gate once and rolls back. Precondition (asserted): the persisted `lane_rebase_moves` named lane-b with `[before, after]` during the run (read it before the rollback drops it, for example from the gate wrapper), and `after` has two parents.
  3. After the rollback assert: lane-b's tip equals its pre-run tip; `refs/spec-kitty/lane-tip/<lane-b>` equals it; no `refs/spec-kitty/auto-rebase/<lane-b>/*` ref remains.
  4. Second run through the real CLI (`consolidate(mission, "squash")`, no `--resume`): exit 0, "Reconciliation verified", no `RESOLUTION_MERGE_UNREVIEWED`, no lane-tip divergence refusal, and no refusal or FAIL text names `after` (the first run's merge).
  5. Control (US6 AS4), a separate test `test_foreign_commit_after_rollback_is_judged_not_reset`: after the rolled-back first run, an operator commit on lane-b (content, by plain git in the lane checkout); the next run refuses `LANE_MOVED_AFTER_APPROVAL` naming that commit, and the commit is still on lane-b afterwards (never reset).
- **Also** run step 4 as `--resume` in a third variant if a record is left after the first run; if the full-restore re-baseline leaves no record (WP03), assert that and say so in history.

### Subtask T056 – Three-lane route: exact siblings, one cycle per conflicting lane, lands

- **Purpose**: FR-008's three-lane variant and FR-002's exact-set control, through the real CLI.
- **Test**: `test_three_lane_route_names_exact_siblings_and_lands`.
- **Steps**:
  1. `mission = add_dependent_and_control_lanes(build_conflicting_lanes_mission(...))` (WP12's shape: lane-c depends on lane-b and overlaps it on `src/pkg/shared.py`; lane-d edits only `src/pkg/other.py`).
  2. First consolidate: the stale refusal for lane-b names `lane-a` as its only sibling (assert the exact set: lane-c and lane-d never named).
  3. `run_route(mission, lane="lane-b", wp_id="WP02", sibling="lane-a", ...)`.
  4. Next consolidate: if lane-c is now stale, its refusal names `lane-b` only (never lane-a or lane-d); run `run_route(mission, lane="lane-c", wp_id="WP03", sibling="lane-b", ...)`.
  5. Final consolidate: exit 0, "Reconciliation verified", and the target holds every lane's content (`blob_present_at`).
  6. SC-001: count the review approvals recorded during the test (status events): at most one per conflicting lane; lane-d gets none; zero printed commands refused for an approved work package.
- **Strategy**: squash, on the coordination topology. Add `--strategy merge` if runtime allows and record the runtime of each in history.

### Subtask T057 – Three-lane: a dependent lane's stamp does not excuse an unreviewed merge

- **Purpose**: the own-lane rule (R-04, architect F8) end to end.
- **Test**: `test_three_lane_dependent_stamp_does_not_excuse_unreviewed_merge`.
- **Steps**: lane-b carries an unreviewed hand merge (WP02 never sent back); lane-c merges lane-b after that merge and is re-approved unforced by an independent reviewer, so lane-c's approval stamp reaches lane-b's merge while lane-b's own stamps do not. Preconditions (asserted): `sha_reachable(lane-c stamp, merge)` is true; no lane-b stamp reaches it; the merge has own content (`git show --remerge-diff --name-only <sha>` lists `src/pkg/shared.py`). Consolidate → exit 1, `RESOLUTION_MERGE_UNREVIEWED` naming lane-b's merge and lane-b; `assert_no_branch_moved`.

### Subtask T058 – Remaining matrix cells: the two-lane route on the LANES topology

- **Purpose**: FR-008 under both strategies on the topology WP12 did not cover (no coordination branch: the Mission branch is the claim base and the status log lives on the target checkout).
- **Test**: `test_route_lands_after_independent_re_review_lanes_topology[squash|merge]`, calling WP12's `build_conflicting_lanes_mission(tmp_path, "lanes", ...)` and `run_route(...)`, then the final consolidate (exit 0, banner, resolved content on the target, approval event unforced with `lane_head` descending from the resolution merge).
- **Also**: N1 on the lanes topology (`test_n1_unreviewed_hand_resolution_is_refused_lanes_topology`), one strategy, asserting the code and `assert_no_branch_moved`.
- **Runtime**: record each cell's runtime in history. Both strategies are required; do not drop a cell for runtime without a runner ruling recorded in history.

## Test Strategy

This WP is the test. Build each fixture once per test (no module-scoped mutation sharing), parametrise narrowly. Marks: `pytest.mark.integration`, `pytest.mark.git_repo`, `pytest.mark.regression`. Unset harness variables per test where behaviour depends on them (`monkeypatch.delenv("SPEC_KITTY_NO_NAG", raising=False)`, `SPEC_KITTY_NON_INTERACTIVE`).

```bash
uv run --frozen pytest -q tests/terminus/test_approved_lane_resolution_route_three_lane.py
uv run --frozen pytest -q tests/terminus/test_approved_lane_resolution_route.py
uv run --frozen pytest -q tests/consolidation/test_rollback_own_lane_moves.py tests/terminus/test_rollback_record_rebaseline.py tests/terminus/test_abort_restores_snapshot.py
uv run --frozen pytest -q tests/architectural/test_no_legacy_terminology.py
make test-fast
```

Do not run `make test-full` or the whole `tests/terminus/` directory. Every test is green with no `xfail` and no `skip`.

Quality gates (tests are typed code too):

```bash
uv run --frozen ruff check tests/terminus/test_approved_lane_resolution_route_three_lane.py
uv run --frozen ruff format --check --force-exclude tests/terminus/test_approved_lane_resolution_route_three_lane.py
uv run --frozen mypy tests/terminus/test_approved_lane_resolution_route_three_lane.py
```

Complexity ≤ 15 per function; no suppressions.

## Tracer notes

Record with `spec-kitty agent tasks add-history WP14 --note "<trace: ...> ..."` (for `traces/tooling-friction.md`, `approach.md`, `design-decisions.md`): every CLI friction met while driving the route (exact command, output), the local helpers you had to add beside the frozen support module and why, the runtime of each cell, and whether the full-restore re-baseline left a record for `--resume` (T055).

## Risks & Mitigations

- **Route gap found late** in the three-lane or lanes-topology route. Mitigation: never an xfail; stop, record with `add-history`, report to the runner, who reopens the owning WP.
- **SC-004 faked by tolerating the merge.** Mitigation: the test asserts lane-b restored, the record ref gone, the lane-tip ref reset, and the next run clean; the foreign-commit control proves nothing is reset blindly.
- **Vacuous three-lane test.** Mitigation: asserted preconditions (dependency recorded, lane-d disjoint, the reach facts of T057) and the exact sibling set in every refusal.
- **Runtime.** Each CLI call is a subprocess (up to 180 s timeout). Keep the matrix explicit and justified in history.
- **Frozen support module.** Import, never edit; local helpers live in this WP's module.

## Review Guidance

- No `xfail` and no `skip` in the module (grep it); any route gap went through history and the runner.
- T055: lane-b restored (tip, lane-tip ref), auto-rebase record ref gone, second CLI run exit 0 naming no commit of the first run's move; the foreign-commit control refuses `LANE_MOVED_AFTER_APPROVAL` and keeps the commit.
- T056: exact sibling sets (lane-d never named; lane-c's refusal names lane-b only), one review cycle per conflicting lane, final exit 0 with the banner.
- T057: preconditions on reach and own content are asserted; the code names lane-b's merge; no branch moved (reflog lengths, no snapshot).
- T058: both strategies on the lanes topology are present; positive paths use only CLI commands plus the two human acts, distinct identities, no `--force`.
- WP12's support module is unchanged in the diff.
- Ruff, format (`--force-exclude`) and mypy ran clean on the new module.

## Progress & Status

Progress, history, and status all live in the status event log
(`status.events.jsonl`) — never in this prompt file. Do **not** hand-edit a
history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history WP14 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP14 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
