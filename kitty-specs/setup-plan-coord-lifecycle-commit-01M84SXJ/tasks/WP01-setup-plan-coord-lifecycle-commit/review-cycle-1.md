---
affected_files: []
cycle_number: 1
mission_slug: setup-plan-coord-lifecycle-commit-01M84SXJ
reproduction_command:
reviewed_at: '2026-11-23T22:10:57Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP01
---

# WP01 review — cycle 1 — CHANGES REQUESTED

Reviewer: `claude::reviewer-renata`. Implementer: `claude::implementer-ivan`. Reviewed head `4f557fc6` (fix `0f3a50f9`, red `a13f0642`, re-pin `e6b19a5e`), base `1890a6c2`.

The fix is right in shape and well tested. The red-first and mutation results are clean, and the materialization finding is a real fix. One blocking defect remains: the new whole-log commit can **erase events already committed on the coordination branch**, and setup-plan still exits 0.

## B1 (blocking): the coordination commit can drop committed status events, silently

`_commit_lifecycle_events_on_coordination` commits the coordination worktree's whole `status.events.jsonl` through `commit_for_mission`. Neither it nor the router checks that the worktree copy still holds every event the coordination branch has committed. `BookkeepingTransaction` does make that check (`coordination/status_surface_guard.py::committed_events_missing_from_worktree`, which refuses `COORD_STATUS_SURFACE_DIVERGED`). Base never committed this log, so this exposure is new to setup-plan.

**Reproduction 1 (the coordination branch moved under its worktree).** Real CLI, `lanes_with_coord`, head `4f557fc6`:
1. Run setup-plan once (scaffold).
2. Another writer advances the coordination branch with one extra event through plumbing (`commit-tree` plus a compare-and-swap `update-ref`); the worktree is not resynced. This is the shape a ref advance or rollback leaves when its checkout resync fails.
3. Write a substantive plan and run setup-plan again.

| | Coordination branch log |
|---|---|
| Before | `[MissionCreated, SpecifyStarted, SpecifyCompleted, PlanStarted, ForeignWriterEvent]` |
| After | `[MissionCreated, SpecifyStarted, SpecifyCompleted, PlanStarted, PlanCompleted]` |

`lifecycle_commit.status == "committed"`, rc 0. **`ForeignWriterEvent` is gone from the authoritative record.**

**Reproduction 2 (the worktree log lags its HEAD).** Same setup, but the worktree log is cut back to its first line before the second run:

| | Coordination branch log |
|---|---|
| Before | `[MissionCreated, SpecifyStarted, SpecifyCompleted, PlanStarted]` |
| After | `[MissionCreated, SpecifyCompleted, PlanStarted, PlanCompleted]` |

`SpecifyStarted` is erased, rc 0. On base the branch is untouched in both cases.

**Why this blocks.**
- It is silent loss of committed status history on the coordination record, which is the status authority for this topology.
- It also disables the backstop. Once the regressed log is committed, HEAD matches the worktree, so neither `committed_events_missing_from_worktree` nor `doctor coordination` (`COORDINATION_WORKTREE_DIRTY`) can see the loss afterwards.
- It contradicts FR-004's intent: success is reported while the record is wrong.

**Requested fix.** Within C-003's "existing seams only":
- Before `commit_for_mission`, run `committed_events_missing_from_worktree(<coordination worktree root>, log)`.
- On missing events, or on `COORD_STATUS_SURFACE_UNREADABLE`, do not commit. Fail loud through the existing `SETUP_PLAN_LIFECYCLE_UNCOMMITTED` refusal, naming the missing committed event ids in the diagnostic, or surface `COORD_STATUS_SURFACE_DIVERGED` itself.
- Add a red-first entry-point test for reproduction 1. A test helper doing `commit-tree` plus `update-ref` on the coordination branch is enough. It must assert that the foreign event survives on the branch and that the exit code is 1.

## S1 (should fix): a raising router has no named code

`commit_for_mission` can raise, for example `CoordWorktreeResolutionError` from `_materialise_coord_worktree` (`commit_router.py:679`, outside its `_OwningSurfaceRefused` catch). That lands in setup-plan's generic `except Exception` arm: `{"error": "..."}`, exit 1, no `error_code`, and no `uncommitted_lifecycle_events`.

FR-004 says "a refused **or failed** coordination commit … with a named error code". Fix: wrap the call, map an exception to a `CommitRouterResult(status="error", diagnostic=str(exc))`, and route it through `_refuse_uncommitted_lifecycle`, with one test that raises from the patched router.

## S2 (should fix): undocumented silent `None` on a coordination topology

`_commit_lifecycle_events_on_coordination` returns `None` when the log file is absent on a coordination topology. The docstring documents `None` only for non-coordination topologies. Because the event writes remain inside the best-effort `try` in `_emit_spec_plan_phase_events` and the `PlanCompleted` block, a swallowed write failure produces a success payload with no `lifecycle_commit` key.

The write *location* is now resolved outside the `try`, which is good. Fix either way:
- document why an absent log is "nothing to record";
- or, preferably, treat an absent log on a coordination topology as a refusal.

The event-write swallowing itself predates this WP; a follow-up note is enough for it.

## S3 (should fix): diff coverage is below the 90% gate

The uncovered lines are:
- 779: the S2 absent-log `None`;
- 798-799: `OSError` in `_setup_plan_events_in_log`;
- 803-804: a malformed JSON line in the same function;
- 1286: the non-JSON console branch of `_refuse_uncommitted_lifecycle`.

Add focused tests:
- a unit test of `_setup_plan_events_in_log` (missing file, a malformed line, a duplicate event type);
- a refused-commit run without `--json`;
- the S2 case.

The B1 and S1 tests also add lines that need coverage.

## Nits

- **N1.** The refusal message says "recorded its lifecycle events (X, Y, Z)", but `_setup_plan_events_in_log` lists every setup-plan event type present in the log, including ones committed by earlier runs. Either say "setup-plan lifecycle events present in the log", or diff against the branch.
- **N2.** `e6b19a5e` edits `tests/integration/test_placement_partition_golden_path.py`, which is outside `owned_files`. It is disclosed in the commit and tracer, so this is fine. Please also name it in the PR's Tests-run section as an out-of-map, out-of-matrix change.

## Checklist results

| # | Check | Result |
|---|---|---|
| 1 | Red first | PASS. On `a13f0642` (base source), 6 fail and 2 pass. Coordination cases fail for the right reasons: coordination worktree dirty (`status.events.jsonl`), and the refusal exited 0. The non-coordination cases pass. |
| 2 | Mutants (all killed) | PASS. Drop the commit: 6 failed. Swallow the refusal: 2 failed. Write to primary: 3 failed. |
| 3 | Commit behaviour | Single and idempotent: PASS (`test_coord_rerun_makes_no_new_commit`). Unrelated dirt not committed: PASS, since `safe_commit` uses `git commit --only -- <log>`; probed, an untracked `probe-notes.md` stays dirty. Coordination branch moved: **FAIL (B1)**. Fail loud on a refusal: PASS. Fail loud on an exception: partial (S1). |
| 4 | Non-coordination byte identity | PASS, probed on base and head. `lanes`: the same commit files (`plan.md` plus `status.events.jsonl`), no `.worktrees/`, 5 commits on both, no `lifecycle_commit` key. `single_branch` and the default pre-settlement Mission are covered by the new parametrized test. |
| 5 | Materialization side effects | Expected, and an improvement. With the coordination worktree removed, base wrote the events to the PRIMARY log (repository root checkout dirty: `plan.md` and `status.events.jsonl`). Head re-establishes the coordination worktree through `write_dir` and commits there, and the root shows only the uncommitted scaffold `plan.md`, as before. That is the spec's stated edge case. Settlement is untouched: setup-plan runs before finalize-tasks, and `write_dir` only materializes an existing coordination branch. The protected-branch guard is untouched: the router resolves the policy, and the coordination branch is not the protected target. |
| 6 | Golden-path re-pin | Justified. The test's claim is about move-task's write. The re-pin only tolerates a missing PRIMARY log, and "primary must not change" still holds. It does not mask the write-to-primary mutant (killed by the coordination tests). |
| 7 | Pre-existing failure | Confirmed. `test_specify_plan_tasks_success_data_key_shape_is_pinned` fails on `origin/main` @ `623c967c` with an extra `kind_normalised` key, and fails on the base too. Not this WP's. |
| 8 | Test runs | See the results below. |
| 9 | Diff coverage | **FAIL (S3).** 88.9% (48 of 54 changed lines) on `mission_setup_plan.py`, measured with `coverage` `patch = subprocess` over the new test file, so the CLI subprocesses are counted. Uncovered: 779, 798-799, 803-804, 1286. |

### Test runs (check 8)

- `make test-fast`: 3222 passed, 7 skipped.
- New file: 8 passed.
- Targeted suite: `tests/coordination/`, the four `tests/specify_cli/cli/commands/agent/test_*setup_plan*` files, the golden-path file and `test_specify_plan_tasks_verbs.py`: 1010 passed, 1 failed. The failure is the pre-existing `kind_normalised` failure (check 7).
- Lint and types: ruff check is clean, `ruff format --check --force-exclude` is clean, and mypy is clean on the changed source and the new test.

### Anti-pattern checklist

| # | Item | Result |
|---|---|---|
| 1 | Dead code | PASS. Every new helper is called from `setup_plan`. |
| 2 | Synthetic fixtures | PASS. Entry-point tests through the real CLI. |
| 3 | Silent empty return | FAIL (S2). |
| 4 | FR coverage | PASS for FR-001 to FR-004. FR-005 is folded. |
| 5 | Frozen surface | N/A. |
| 6 | Locked decision | PASS. |
| 7 | Shared-file ownership | PASS, with N2 noted. |
| 8 | Production fragility | PASS. `typer.Exit(1)` is a documented fail-loud. |

B1 is a FAIL under check 3 and is the reason for this rejection.
