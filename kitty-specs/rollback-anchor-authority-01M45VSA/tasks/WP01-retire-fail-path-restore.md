---
work_package_id: WP01
title: Retire the FAIL-path restore (#5666)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-010
- SC-003
planning_base_branch: issue-5686-rollback-anchor
merge_target_branch: issue-5686-rollback-anchor
branch_strategy: Planning artifacts for this mission were generated on issue-5686-rollback-anchor. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5686-rollback-anchor unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-rollback-anchor-authority-01M45VSA
base_commit: 22fb364234b934d77b1efba895bd1dc5e3d1c9bb
created_at: '2026-10-05T11:37:06.662625+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Single restore path
history:
- at: '2026-10-05T12:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/phase_gate.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/phase_gate.py
- tests/consolidation/test_rollback_anchor_p0_repro.py
- tests/consolidation/test_single_rollback_authority.py
- tests/consolidation/test_refuse_restores_target.py
- tests/consolidation/test_merge_state_authority.py
- tests/terminus/test_rollback_door.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Retire the FAIL-path restore (#5666)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill (or `spec-kitty agent profile show python-pedro`) to load the agent profile in the frontmatter. Follow its guidance before you read the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Also run `spec-kitty charter context --action implement --json` and apply it.

---

## Objectives & Success Criteria

After a reconciliation FAIL or REFUSE, the target is rolled back **only** by the #5385 single door. That is `executor._report_rollback` → `rollback.rollback_to_snapshot`, which compare-and-swaps against the tip this run *recorded*. A commit another actor landed on top of the landing stays reachable, and the report says `NOT restored ... moved by another actor`. The second restore path, `phase_gate._rollback_target_after_failed_reconciliation`, which used the *live* tip as its CAS expectation, is deleted, and an AST pin keeps it deleted.

Done when:
- `tests/consolidation/test_rollback_anchor_p0_repro.py::test_failed_reconciliation_rollback_keeps_a_concurrent_target_commit` is rewritten to drive the gate through the door, carries **no** `p0_repro` marker, and was **red on the base** (show this in the activity log: run the rewritten test against the unchanged `phase_gate.py` first) and is green after the fix.
- `_rollback_target_after_failed_reconciliation` no longer exists anywhere in `src/`.
- `tests/consolidation/test_single_rollback_authority.py` lists it in `_RETIRED_NAMES` and gains a scan proving that no `restore_branch_ref(...)` call of any kind exists in the consolidation executor family (`tests/consolidation/executor_family.py::EXECUTOR_FAMILY` modules) outside `consolidation/rollback.py`. A self-mutation case must show the scan fires on a synthetic non-resync restore.
- The positive control (US1 AS3) passes. With no foreign commit, a FAIL inside the door fully restores the target to the snapshot, and the primary checkout is clean.

## Context & Constraints

- Spec: `kitty-specs/rollback-anchor-authority-01M45VSA/spec.md`, US1 and FR-001/FR-002/FR-010. Grounding: `research/code-grounding.md` §2 (#5666) and §5.
- Charter: red-first (SO #4), single canonical authority, C-001 (never add a restore path), C-002 (no destructive recipe in any message), C-003 (do NOT edit `consolidation/reconciliation.py`).
- `typer.Exit(1)` raised by the gate already sits inside the door `try` in `executor._run_lane_based_consolidation_locked` (see the `#5385` comment there). Deleting the helper call is enough for the restore to happen through the door. Verify this; do not assume it.
- The door's `restore_branch_ref(resync_checkouts=True)` resyncs the primary checkout, which replaces the helper's `_refresh_primary_checkout_after_merge`. If the positive control shows a dirty-checkout refusal, investigate before changing anything outside your owned files, and report it.
- WP02 runs in parallel and edits `consolidation/rollback.py` and `consolidation/state.py`. Do **not** touch those files. WP03 (later) removes the `p0_repro` marker from the *other* test in the repro file (the #5686 one); leave that test unchanged.
- **Blast radius (post-tasks squad HIGH):** the helper used to reset the target BEFORE the door ran, so the door's own restore of the target, with its checkout resync, has never run on a FAIL/REFUSE. About 15 terminus FAIL/REFUSE suites assert the target is back at its pre-run tip (`test_mixed_lane_canceled_content_verdicts`, `test_mixed_lane_closed_world`, `test_canceled_dependency_fast_forward_verdicts`, `test_repro_4945/4977/4981`, `test_mixed_lane_fail_recovery_and_attestation`, and others). Run all of `tests/terminus` and `tests/integration -k "merge or consolidat"`. If the door's resync refuses on a checkout state the helper used to hard-reset, root-cause it and report it; do not re-add a reset. Re-pins of those suites are allowed as ownership-map leeway, each with a one-line rationale.

## Branch Strategy

- **Strategy**: lanes. The execution worktree is allocated per computed lane from `lanes.json`; use the workspace `spec-kitty implement WP01` prints.
- **Planning base branch**: `issue-5686-rollback-anchor`
- **Merge target branch**: `issue-5686-rollback-anchor`

## Subtasks & Detailed Guidance

### Subtask T001 – Rewrite the #5666 reproduction (red first)

- **Purpose**: the current test imports and calls the helper directly, so it cannot survive the helper's deletion. The behaviour it guards must be exercised at the production entry point (non-vacuity rule: a helper-only test can stay green while the wiring is broken).
- **Steps**:
  1. Keep the test's name and its assertion (the concurrent commit stays reachable from the target), and keep the module docstring's #5666 narrative, updated. Remove `@pytest.mark.p0_repro(issue=5666)`.
  2. Drive it through the door. Use the in-process harness in `tests/terminus/` (`build_lanes_mission` / `run_terminus` in `tests/terminus/lanes_fixture.py` and `conftest.py`) to run a real consolidate. Inject the concurrent commit by wrapping the gate phase `phase_gate._phase_reconcile_before_teardown` (`monkeypatch` the name where the driver looks it up). The wrapper commits a file on the target branch in the repository root checkout, then calls the original. The un-attributable foreign path makes the real gate FAIL, which is the #5666 mechanism.
  3. Assert: consolidate exits non-zero; the foreign commit is an ancestor of the target; the rollback report contains `NOT restored` for the target with "moved by another actor"; the foreign file is still present in the primary checkout.
  4. If the terminus harness cannot be imported cleanly from `tests/consolidation/`, put the door-driven test in `tests/terminus/test_rollback_door.py` (also yours). In the repro file keep a thin test with the same name that calls the door helper `executor._report_rollback` on a `_MergeRunState` whose state has a recorded post tip (snapshot → landing), after the foreign commit. Prefer the full-door version.
  5. Commit the red test first, as its own commit, and record the red run in the activity log.

### Subtask T002 – Delete the helper

- **Steps**: in `phase_gate.py`, remove the `if result.status in (VerifyStatus.FAIL, VerifyStatus.REFUSE): _rollback_target_after_failed_reconciliation(run)` call and the function. Rewrite the long comment above it to say the single door restores (CAS against the recorded post tip) and that the gate itself moves nothing. Remove the imports that become unused (`restore_branch_ref`, `RefRestoreError`, `_refresh_primary_checkout_after_merge` if unused). Update the `_phase_reconcile_before_teardown` docstring.
- Check that `VerifyStatus` and the other remaining imports are still used. Run ruff.

### Subtask T003 – Widen the AST pin

- **Steps** in `tests/consolidation/test_single_rollback_authority.py`:
  - Add `"_rollback_target_after_failed_reconciliation"` to `_RETIRED_NAMES`.
  - Add a scanner (reuse `_calls_named`) over the source of every module in `EXECUTOR_FAMILY` plus `consolidation/rollback.py`. It asserts that every `restore_branch_ref` call is in `rollback.py`, with a concrete floor of at least one call found in `rollback.py` (non-vacuous).
  - Add a self-mutation test: a synthetic phase-module source with a plain `restore_branch_ref(repo, b, sha, expected_current_sha=x)` call must be flagged.
  - Update the module docstring's rule list.
- Do not add an allowlist (C-005 / charter SO #5: start empty).

### Subtask T004 – Re-pin the gate tests

- `tests/consolidation/test_refuse_restores_target.py`: its tests call the gate outside the door and assert `main == pre_sha`, which pins the helper as the restorer. Re-pin each one (stale → re-pin):
  - FAIL / REFUSE restore tests → assert that the gate itself moves nothing (target still at the landing after `_phase_reconcile_before_teardown` raises `Exit(1)`), and that the door (`executor._report_rollback` with a recorded post tip) restores it.
  - "target moved elsewhere" → foreign commit after the recorded post tip: the door reports NOT_RESTORED and the commit is kept. This is a per-PR #5666 guard.
  - "unknown pre-mutation tip" → no snapshot: the door says nothing was rolled back. Or delete it if fully redundant, with a one-line rationale in the activity log.
  - `test_pass_never_rolls_back` stays.
- `tests/consolidation/test_merge_state_authority.py::TestRollbackTargetAfterFailedReconciliation`: unit tests of the retired helper; delete the class (stub → delete). Keep everything else in that file.

### Subtask T005 – Door-level FAIL tests in `tests/terminus/test_rollback_door.py`

- Run the positive control on BOTH the lanes and the coord topology fixtures.
- Add (or host, per T001 step 4) an end-to-end reconciliation FAIL with a concurrent target commit, plus the US1 AS3 positive control on the **same fixture builder**:
  - no foreign commit + a forced gate FAIL (e.g. wrap the gate so the verifier returns FAIL, or plant canceled content with `plant_canceled_commit` as other terminus tests do);
  - expect a full restore (`Rollback to the pre-consolidation snapshot` with `restored <target>`), the target at its pre-run tip, and `git status --porcelain` clean in the repository root checkout.

## Test Strategy

Run, and record the commands and counts in the activity log:
```bash
uv run --frozen pytest tests/consolidation/test_rollback_anchor_p0_repro.py tests/consolidation/test_single_rollback_authority.py tests/consolidation/test_refuse_restores_target.py tests/consolidation/test_merge_state_authority.py tests/terminus/test_rollback_door.py -q
uv run --frozen pytest tests/consolidation tests/terminus -q -n auto --dist loadfile
uv run --frozen pytest tests/integration -k "merge or consolidat" -q -n auto --dist loadfile
uv run --frozen pytest tests/architectural/test_destructive_op_routing.py tests/architectural/test_no_legacy_terminology.py -q
uv run --frozen ruff check <changed files> && uv run --frozen ruff format --check --force-exclude <changed files>
uv run --frozen mypy src/specify_cli/consolidation/phase_gate.py
```
Never run `make test-full` or a bare `tests/architectural/`.

## Risks & Mitigations

- The door may report `NOT restored` for a dirty primary checkout where the helper used to hard-reset. The positive control catches this; report it rather than adding a reset.
- Any other test that imports the helper: `grep -rn _rollback_target_after_failed_reconciliation tests src`.

## Review Guidance

- Red-before-green evidence for T001.
- No new restore path, and no `restore_branch_ref` left in `phase_gate.py`.
- Each re-pinned test asserts behaviour at the door, and none was simply deleted to get green (except the helper's unit-test class).

## Activity Log

- 2026-10-05T12:00:00Z – system – Prompt created.
- 2026-10-05T14:10:00Z – python-pedro – T001 red: rewrote `test_failed_reconciliation_rollback_keeps_a_concurrent_target_commit` to drive a real in-process consolidate (LANES fixture) through the door; a wrapper around `executor._phase_reconcile_before_teardown` commits `teammate-commit.txt` on the target in the root checkout, the real gate FAILs on it. No `p0_repro` marker. Red on the unchanged `phase_gate.py` (commit 3b1b24db): `uv run --frozen pytest tests/consolidation/test_rollback_anchor_p0_repro.py -q` -> 1 failed, 1 deselected: "the reconciliation-FAIL rollback reset develop to e8d25ec and discarded the concurrent commit 6dc4c1d ... unchanged develop (already at e8d25ec)".
- 2026-10-05T14:40:00Z – python-pedro – T002: deleted `_rollback_target_after_failed_reconciliation` and its call; gate comment/docstrings now say the door restores and the gate moves nothing; dropped unused imports (`restore_branch_ref`, `RefRestoreError`, `_refresh_primary_checkout_after_merge`, `VerifyStatus`). Verified the gate's `typer.Exit(1)` lands in the #5385 door: same test green (1 passed). Commit e8d317de.
- 2026-10-05T14:40:00Z – python-pedro – T003: `_RETIRED_NAMES` += the helper; new `scan_restores` + `test_no_restore_of_any_kind_in_the_executor_family_outside_the_authority` (EXECUTOR_FAMILY + rollback.py, floor: >=1 call in rollback.py); self-mutation `test_scanner_flags_a_non_resyncing_restore_in_a_phase_module` and `test_scanner_flags_a_retired_fail_path_restore`. Manually confirmed the new scan flags base `phase_gate.py` (`_rollback_target_after_failed_reconciliation`) while the resync-only scan returned []. No allowlist.
- 2026-10-05T14:40:00Z – python-pedro – T004: `test_refuse_restores_target.py` re-pinned: FAIL/REFUSE (parametrized) -> gate moves nothing, door (`_report_rollback` with snapshot + recorded post tip) restores; target-moved-elsewhere -> foreign commit after the recorded post tip kept, door reports NOT restored / moved by another actor (per-PR #5666 guard); unknown pre-mutation tip -> door says "Nothing was rolled back"; `test_pass_never_rolls_back` kept. Deleted `TestRollbackTargetAfterFailedReconciliation` (unit tests of the retired helper).
- 2026-10-05T14:40:00Z – python-pedro – T005: `tests/terminus/test_rollback_door.py` + positive control (US1 AS3) and concurrent-commit FAIL, each parametrized over lanes and coord fixtures. Positive control: full restore (`restored <target> <post> -> <pre>`, no NOT restored in the report), target at pre-run tip, root checkout clean apart from the untracked `.kittify/` consolidation record. The door's resync did not refuse anywhere.
- 2026-10-05T14:40:00Z – python-pedro – Leeway (outside owned_files): `tests/specify_cli/cli/commands/test_merge_coord_topology_1772.py` and `tests/specify_cli/test_specify_topology_flag.py` – removed the stale patch of `phase_gate._refresh_primary_checkout_after_merge` (the import no longer exists, mock.patch would raise). `tests/terminus/test_rollback_restores_refs.py::test_gate_fail_restores_target_and_coordination_branch` – re-pinned the target line from "unchanged (already at <pre>)" to the door's "restored <post> -> <pre>" (the old line only held because the gate restored first); commit e3552f24.
- 2026-10-05T15:30:00Z – python-pedro – Tests: owned files `uv run --frozen pytest tests/consolidation/test_rollback_anchor_p0_repro.py tests/consolidation/test_single_rollback_authority.py tests/consolidation/test_refuse_restores_target.py tests/consolidation/test_merge_state_authority.py tests/terminus/test_rollback_door.py -q -n0` -> 77 passed, 1 deselected (#5686 p0_repro). `pytest tests/consolidation tests/terminus -q -n auto --dist loadfile` -> 1894 passed, 1 skipped, 5 xfailed, 1 failed (test_rollback_restores_refs re-pin above; re-run of that file after re-pin: 3 passed). `pytest tests/integration -k "merge or consolidat" -q -n auto --dist loadfile` -> 88 passed, 1 skipped, 1 failed: `test_merge_lane_planning_data_loss.py::test_bare_slug_coord_mission_consolidates_onto_a_protected_target` (MERGE_UNSAFE_WORKTREE_DIRTY on untracked coord status files) – PRE-EXISTING, also red with base 22fb3642 `phase_gate.py` (1 failed), not caused by this WP. `pytest tests/architectural/test_destructive_op_routing.py tests/architectural/test_no_legacy_terminology.py tests/specify_cli/cli/commands/test_merge_coord_topology_1772.py tests/specify_cli/test_specify_topology_flag.py -q -n0` -> 143 passed. `make test-fast` -> 2279 passed, 8 skipped. ruff check + `ruff format --check --force-exclude` on all changed files clean; mypy (repo .venv mypy 1.20.2 with `--python-executable .venv/bin/python`) on phase_gate.py: no issues (the worktree venv has no mypy installed).
