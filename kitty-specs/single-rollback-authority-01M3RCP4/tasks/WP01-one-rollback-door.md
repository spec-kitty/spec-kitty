---
work_package_id: WP01
title: One rollback door for the post-mutation span
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-004
- FR-005
- FR-008
- FR-009
- NFR-002
- NFR-003
- NFR-004
- C-002
- C-004
planning_base_branch: claude/5385-single-rollback-authority-qqt180
merge_target_branch: claude/5385-single-rollback-authority-qqt180
branch_strategy: Planning artifacts for this mission were generated on claude/5385-single-rollback-authority-qqt180. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into claude/5385-single-rollback-authority-qqt180 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-single-rollback-authority-01M3RCP4
base_commit: e0235952dc5794a1f0a4129183d8d117ba430752
created_at: '2026-09-30T05:55:56.665110+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T013
phase: Phase 1 - Core
agent: claude
history:
- at: '2026-09-30T06:10:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/executor.py
create_intent:
- tests/terminus/test_repro_5385_rollback_door.py
execution_mode: code_change
owned_files:
- src/specify_cli/consolidation/executor.py
- tests/terminus/test_repro_5385_rollback_door.py
- tests/consolidation/test_single_rollback_authority.py
- tests/consolidation/test_executor_rollback_wiring.py
- tests/consolidation/test_executor_option_a_revert_helpers_2711.py
- tests/consolidation/test_executor_coverage.py
- tests/consolidation/test_issue_2367_bake_strand.py
- tests/consolidation/test_issue_2786_revert_failure_split_brain.py
- tests/consolidation/test_executor_coord_reconcile.py
- tests/consolidation/test_issue_4764_bake_rollback_on_done_failure.py
- tests/specify_cli/cli/commands/test_merge_coord_worktree_resync_1826.py
- tests/architectural/test_coord_rollback_coherence_guard.py
- tests/terminus/test_repro_5318_abort.py
- tests/consolidation/test_done_bookkeeping_rollback_coherence.py
- tests/consolidation/test_issue_4474_topology_aware_bake.py
role: implementer
---

# WP01 — One rollback door for the post-mutation span

## ⚡ Do This First: Load Agent Profile

Before reading anything else, load your assigned profile: `/ad-hoc-profile-load python-pedro` (or `spec-kitty agent profile show python-pedro`). Work under its governance, then read `.kittify/charter/charter.md` and `spec-kitty charter context --action implement`.

## Objective

`spec-kitty consolidate` must undo its own branch moves in exactly one way: the compare-and-swap restore `consolidation/rollback.py::rollback_to_snapshot`. Today only the reconciliation gate and `--abort` call it (`executor.py:3806-3809` and `cli/commands/consolidate.py::_abort_restore_or_keep_record`). Every other exit after the first mutation relies on per-phase `git revert` helpers or nothing, so the target can stay advanced (issue #5385: a LANES mission on protected `main` squashes, then `BookkeepingPolicyRefused` escapes `_phase_record_done_and_project` as a raw traceback with the target advanced).

This WP wraps the whole post-mutation span in one door, deletes the revert-based helpers, re-pins the tests that pinned the older contract, and grows the AST pin.

Read first: `kitty-specs/single-rollback-authority-01M3RCP4/spec.md`, `plan.md`, `research.md`, `contracts/rollback-door.md`; ADR `docs/adr/3.x/2026-09-19-1-terminus-safety-invariant.md` (Amendment 2026-09-29, A1-A5 and "Remaining authorities"); `src/specify_cli/consolidation/rollback.py` in full.

## Branch Strategy

Planning base and final merge target: `claude/5385-single-rollback-authority-qqt180`. The execution worktree is allocated per computed lane from `lanes.json` by `spec-kitty agent action implement WP01 --agent claude`; work only in the path that command returns.

## Subtasks

### T001 — Red-first real-git repro (FIRST, before any product change)

Create `tests/terminus/test_repro_5385_rollback_door.py`, markers `[pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]`, module docstring naming #5385 and the contract.

- Fixture: `tests.terminus.lanes_fixture.build_lanes_mission(tmp_path, wps=("WP01","WP02"), target_branch="develop", mid8=...)` (unprotected target, so the run gets past the done bookkeeping). Use a distinct `mid8` per test.
- Drive the real executor in-process: `executor._run_lane_based_consolidation(mission.repo, mission.slug, push=False, delete_branch=None, remove_worktree=None, assume_yes=True)` with `monkeypatch.chdir(mission.repo)` and `HOME` pointed at `mission.home` (check `tests/terminus/conftest.py` for the helper the other in-process tests use; if every terminus test uses the subprocess `run_terminus`, use in-process anyway: the injection needs `monkeypatch`).
- Injection: for each phase name in `("_phase_merge_lanes", "_phase_bake_and_pre_target_done", "_phase_mission_to_target", "_phase_capture_and_baseline", "_phase_record_done_and_project", "_phase_porcelain_invariant", "_phase_commit_and_assert")`, parametrize a test that replaces `executor.<phase>` with a wrapper that calls the ORIGINAL attribute (so the real mutation happens and its post tips are recorded) and then raises. Parametrize the raised thing over at least `typer.Exit(1)` and `RuntimeError("planted")` (the #5385 uncaught shape). Only the injection is patched; everything else is real git (NFR-004).
- Also parametrize `KeyboardInterrupt()` for at least the `_phase_mission_to_target` case (an `except Exception` door must fail it).
- Assertions, per case: exit is non-zero (`typer.Exit` code 1, or the `RuntimeError` propagates); `git rev-parse` of the target, the mission branch (`mission.coord_branch` holds the LANES mission branch name) equal their pre-run values; every lane branch equals its pre-run value; the output (capture `executor.console` or `capsys`) contains the rollback report header `Rollback to the pre-consolidation snapshot`.
- Vacuity guard: at least the `_phase_mission_to_target` and later cases must prove the target really moved during the run (reflog of the target grew by >= 2 entries and the newest entry is the pre-run SHA), mirroring `tests/terminus/test_repro_5318.py`'s reflog guard.
- `_phase_merge_lanes` case: its own vacuity guard (the mission branch reflog moved during the run and the newest entry is the pre-run SHA).
- US1 AC5 case: dirty the target checkout with a non-residue file after `_phase_mission_to_target` and raise `typer.Exit(1)` from `_phase_porcelain_invariant`; assert the target is reported `NOT restored`, the mission branch IS restored, the record is kept, exit non-zero.
- SC-004 / FR-009 case: after a `_phase_record_done_and_project` failure, assert the record has `completed_wps == []` and `mission_number_baked` is False; then remove the injection, re-run, and assert exit 0 with both lane files on the target.
- Add one real-CLI case for the literal #5385 shape: `build_lanes_mission(..., target_branch="main")`, `run_terminus(mission, ["consolidate", "--mission", slug, "--yes"])`; assert non-zero exit and `main` at its pre-run SHA. (After WP02 this case is refused before mutation; the assertions hold either way.)
- Run it on the unmodified code and record the RED output (which assertion, which phases) in `kitty-specs/single-rollback-authority-01M3RCP4/traces/approach.md` via the orchestrator (you may paste it into your final report instead; do not edit kitty-specs from the lane).

### T002 — One door in the driver

In `_run_lane_based_consolidation_locked` (`executor.py` ~3760-3814):

1. Capture `anchor_before = run.state.reconciliation_passed_target_sha` BEFORE the `if not _resume_reconciliation_already_passed(run):` block.
2. Put the whole block (the phase list AND the `else` baseline branch) plus `_phase_reconcile_before_teardown(run)` inside ONE `try`. Remove the inner `try/except` around `_phase_merge_lanes` and the separate gate `try`.
3. Handlers, in this order:
   ```python
   except typer.Exit as exc:
       if exc.exit_code:
           _report_rollback(run, anchor_before=anchor_before)
       raise
   except BaseException:
       _report_rollback(run, anchor_before=anchor_before)
       raise
   ```
   `typer.Exit` subclasses `RuntimeError`, so the `typer.Exit` clause must come first and a zero exit must not roll back.
4. `_report_rollback` already refuses to raise on a rollback failure. Keep that; make sure its `except Exception` also covers a failure in the anchor reset/`save_state` at its top (move that inside the guarded region) so a rollback problem can never replace the original error.
5. Keep the phase calls INLINE in `_run_lane_based_consolidation_locked` (its complexity is 6 today). Do NOT extract a span helper: `tests/consolidation/test_executor_phase_boundary.py:95` and `tests/consolidation/test_reconciliation.py:970,984` read the driver's source with `inspect.getsource` and index the literal phase calls.
7. Positive controls (unit, in `tests/consolidation/test_executor_rollback_wiring.py`): a spy on `_report_rollback` proves `typer.Exit(0)` raised inside the span does NOT roll back and propagates; `typer.Exit(1)`, `RuntimeError` and `KeyboardInterrupt` each call it exactly once and propagate unchanged; `rollback.rollback_to_snapshot` raising, and `save_state` raising inside `_report_rollback`, both leave the ORIGINAL exception propagating and print the "Rollback could not complete" line.
6. Update the driver comments: the scope note about `_rollback_to_pre_mutation_checkpoint` (lines ~3727-3750) and the gate comment (~3796-3805) describe the old design; rewrite them in two or three sentences.

### T003 — Retire the revert-based helpers

Delete, with their docstrings and call sites:
- `_reset_coord_to_checkpoint`, `_revert_coord_done_commit`, `_rollback_to_pre_mutation_checkpoint`, `_revert_orphan_target_bake_commit`.
- `_capture_pre_mutation_coord_checkpoint` and the `_MergeRunState.pre_mutation_coord_ref` / `pre_mutation_coord_sha` run fields, IF nothing else reads them (`rg -n "pre_mutation_coord_(ref|sha)" src/` — the PERSISTED `state.pre_mutation_coord_sha` / `state.pre_mutation_coord_ref` in `consolidation/state.py` and `_resolve_pre_mutation_coord_sha` STAY; `rollback.capture_pre_mutation_snapshot` seeds from them).
- `_MergeRunState.pre_bake_target_baseline_sha` and the line in `_reanchor_baseline_past_primary_tree_bake` that sets it; keep the re-anchor of `run.target_baseline_sha` (it still scopes `_target_branch_still_at_baseline`).

Rewrite the remaining callers:
- `_restore_pre_target_if_at_baseline`: keep only `if run.done_marked_before_target and still_at_baseline: _restore_and_guard_coord_coherence(run, run.pre_target_bookkeeping_snapshots)` (working-tree bytes + strand marker). Keep its `@_records_post_mutation_tips` decorator only if it can still move a ref; if it cannot, drop the decorator and update the parametrize in `test_executor_rollback_wiring.py` accordingly. Update its docstring: the ref undo is the driver door's job.
- `_phase_bake_and_pre_target_done` except path: keep `_restore_and_guard_coord_coherence(...)` and `raise`; delete the orphan-bake branch.
- `_CoordCheckpoint` stays (still used by `_capture_coord_checkpoint`, `_resolve_pre_mutation_coord_sha`, `run.coord_checkpoint`); trim its docstring's references to deleted helpers.
- In `_restore_and_guard_coord_coherence`, DROP the `if run.is_resume: _heal_pending_coord_reconcile(run)` call: with the coordination revert gone, the marker now records a strand on every coordination byte restore, and that heal is a forward `git revert` (`coordination/coherence.py::repair_coord_strand`) that would commit inside the span on every resume. The resume-start heal in the driver (`if run.is_resume: _heal_pending_coord_reconcile(run)`, before the phase list) stays and is the only caller.
- Keep `_restore_and_guard_coord_coherence` and its decorator: the byte restores include `state.json` (`merge_state_path`), and the decorator's `record_post_mutation_tips` re-saves the in-memory state afterwards (post-spec squad H4). Add a focused unit test that a byte restore followed by the recorder leaves `post_mutation_refs` intact on disk.
- The authority's `_clear_bookkeeping` clears `mission_number_baked`, `completed_wps` and `pending_coord_reconcile` (when the coordination branch was restored) after a full restore; that replaces the flag clear the orphan-bake revert used to do (`test_issue_4764_bake_rollback_on_done_failure.py:356`).

Search afterwards: `rg -n "git.*revert|\"revert\"" src/specify_cli/consolidation/executor.py` must return nothing that undoes a phase (the coordination strand heal lives in `coordination/coherence.py::repair_coord_strand`, out of scope). Also `rg -n "_reset_coord_to_checkpoint|_revert_coord_done_commit|_rollback_to_pre_mutation_checkpoint|_revert_orphan_target_bake_commit|pre_bake_target_baseline_sha" src tests docs` — fix every src reference; tests are T004; docs are WP03 (leave a list for it in your report). Also `src/specify_cli/consolidation/ordering.py:588` has a comment naming `_capture_pre_mutation_coord_checkpoint` — update it (one-line out-of-map edit, note it).

### T004 — Re-pin the old-contract tests (DM-01M3RCRDBS2RKWVVZH07AZ1B4M)

Judge each test, do not delete coverage blindly (charter Standing Order 4: stale -> re-pin, stub -> delete, valid -> keep):
- `tests/consolidation/test_executor_option_a_revert_helpers_2711.py`: unit tests of `_revert_coord_done_commit`; delete those cases with the helper. Keep and keep passing any `_capture_pre_target_coord_ref_sha` cases (lines ~200-231).
- `tests/consolidation/test_executor_coverage.py`: patches of `_restore_pre_target_if_at_baseline` (lines ~328-511); keep them where the function still exists; adjust expectations for its narrower body.
- `tests/consolidation/test_executor_rollback_wiring.py`: the recorder parametrize (~288) and `test_restore_pre_target_if_at_baseline_records` (~299) that monkeypatches `_revert_orphan_target_bake_commit`.
- `tests/specify_cli/cli/commands/test_merge_coord_worktree_resync_1826.py:431` and `:478`: re-pin to the new contract. After the injected failure: the coordination/mission branch and target are back at pre-run tips; the record's `completed_wps == []`; committed coordination events carry no `done` for the merged WPs; a resume (or re-run) after removing the injection succeeds and reaches `done`. Rename the tests to say what they now assert; keep the docstring's history line ("pre-#5385 contract kept committed done; the single rollback door now restores the snapshot").
- `tests/consolidation/test_issue_2367_bake_strand.py:382` (expects a strand after the failure): re-pin: no strand remains, the coordination branch is at its snapshot, the marker is cleared, and a later resume is coherent.
- `tests/consolidation/test_issue_2786_revert_failure_split_brain.py` and `tests/consolidation/test_executor_coord_reconcile.py::test_revert_failure_strand_marks_and_resume_reconciles` force `git revert` to fail. That mechanism no longer exists in the executor. Re-pin the class to its successor failure: the authority cannot restore the coordination branch (for example another actor moved it, or its checkout is dirty), the rollback reports it NOT restored, `pending_coord_reconcile` stays set, the record is kept, and the resume-start heal still reconciles. If a case only exercised the deleted revert call, delete it and say so in your report.
- `tests/consolidation/test_issue_4764_bake_rollback_on_done_failure.py:305`: tree equality and `mission_number` absence should hold; the `mission_number_baked is False` assertion now holds via the authority's `_clear_bookkeeping`. Update the comment.
- `tests/architectural/test_coord_rollback_coherence_guard.py:165-257` drives the full consolidation through `test_issue_2367_bake_strand._run_bake_failing_merge` and asserts, as a precondition, that a committed coordination `done` strand SURVIVES the bake failure. After the door that is false. Re-pin: drive its falsifiers at the PHASE level (call `_phase_bake_and_pre_target_done` directly, outside the door) so the strand-marking guard is still exercised, and add one driver-level case asserting the coordination branch is restored and `pending_coord_reconcile` is cleared.
- Fix the stale docstrings in `test_done_bookkeeping_rollback_coherence.py:7-19` and `test_issue_4474_topology_aware_bake.py:10` (they name retired helpers).
- Run unchanged and confirm green: `test_issue_2711_merge_rollback_resume_coherence.py`, `test_done_bookkeeping_rollback_coherence.py`, `test_merge_rollback_resume_coherence.py`, `tests/integration/test_merge_resume.py`, `tests/architectural/test_destructive_op_routing.py` (op ordinals may shift when `revert` calls disappear; re-pin census entries with a one-line reason), `tests/terminus/test_repro_5318*.py`, `test_repro_5332.py`, `test_repro_refuse_restores_all.py`, `tests/consolidation/test_refuse_restores_target.py`, `test_rollback_authority.py`.

### T005 — Grow the AST pin

`tests/consolidation/test_single_rollback_authority.py`:
- New rule: every call in the driver (or its extracted span helper) to a phase in the set `{_phase_merge_lanes, _phase_baseline_and_surface, _phase_bake_and_pre_target_done, _capture_pre_target_gate_artifacts, _phase_mission_to_target, _switch_write_checkout_after_single_branch_landing, _phase_capture_and_baseline, _phase_record_done_and_project, _phase_porcelain_invariant, _phase_commit_and_assert, _phase_reconcile_before_teardown}` sits inside a `try` whose handlers call `_report_rollback`, and a handler catches `BaseException`. Concrete floor: at least 11 such calls found.
- New rule: no function in `consolidation/executor.py` builds a `git ... revert` argv (scan string constants `"revert"` inside `ast.List`/call args) — a concrete denylist of the four retired names as well.
- Keep the existing caller allow-list (still two callers).
- New rule: `_heal_pending_coord_reconcile` is called only from the driver (the resume-start site), never from a restore primitive inside the span.
- Self-mutation cases: a synthetic driver with one phase call outside the `try`; one whose handler catches only `typer.Exit`; a synthetic executor that defines `_reset_coord_to_checkpoint` or calls `["git", "revert", ...]`; each must make the scanner report a violation. Replace `test_driver_gate_call_is_wrapped_with_the_rollback_report` rather than duplicating it.

### T013 — Re-home the `--abort` repro fixture (moved here from WP02: it goes red the moment T002 lands)

`tests/terminus/test_repro_5318_abort.py::_crashed_lanes_run` (:61-72) relies on the #5385 crash leaving residue, and `test_5318_abort_after_a_crashed_resume_still_restores` (:238-240) runs a real `--resume` that needs the same residue. After T002 the crash is rolled back in-process. Replace the residue source with a documented hard-kill simulation:
- run the real CLI through an inline `python -c` wrapper (build it in this file; copy `run_terminus`'s env: `PYTHONPATH` = the worktree `src`, `HOME` = `mission.home`, `SPEC_KITTY_NO_UPGRADE_CHECK=1`, no `VIRTUAL_ENV`) that replaces `specify_cli.consolidation.executor._report_rollback` with a function calling `os._exit(137)`, then calls `specify_cli.main()` with the consolidate argv;
- use the wrapper for BOTH the first crashing run and the crashed `--resume`;
- keep every precondition assert and test body; docstring: the injection models a hard kill between the crash and the in-process rollback (the only way a real run still leaves this residue).
WP02 will add one line to the wrapper that disables its new preflight.

### T006 — Validate

- `ruff check` and `ruff format --check` on changed files, `mypy` on `src/specify_cli/consolidation/executor.py` (repo config). Zero new issues, no suppressions.
- Targeted runs (never a whole directory of architectural/e2e/perf): the T001 file, `tests/terminus/test_repro_5318_abort.py`, every file edited in T004, the "run unchanged" list above, `tests/consolidation/test_single_rollback_authority.py`, `tests/consolidation/test_executor_phase_boundary.py`, `tests/consolidation/test_executor_terminus_integrity.py`, plus `make test-fast`. Use `.venv/bin/python -m pytest ... -n 4 --dist loadfile`.
- Planted-break proof: temporarily re-add the inner `_phase_merge_lanes`-only `try` and move one phase call out of the door; show the pin and at least one T001 case go red; revert. Record the commands and counts in your report.
- Classify any red per CLAUDE.md "baseline-red gotcha" by re-running it on `c34481d7` before treating it as yours.

## Definition of Done

- T001 red on `c34481d7`, green now; its RED output is in your report.
- The four helpers and `pre_bake_target_baseline_sha` are gone from `src/`; the pin forbids their return.
- Every touched function complexity <= 15; ruff/format/mypy clean.
- Commits: one per subtask where practical, conventional messages with `(#5385)`, each ending with the session's `Co-Authored-By` / `Claude-Session` trailers the orchestrator gives you.

## Risks and reviewer guidance

- Reviewer: check that no handler swallows the original exception; that `typer.Exit(0)` is not rolled back; that the resume short-circuit (`_resume_reconciliation_already_passed`) path still rolls back only on a gate failure; that re-pinned tests assert the NEW contract with real SHAs (no mocked git).
- Known residuals (spec "Known residuals") are out of scope; do not try to fix lane auto-rebase commits or the resume-start heal.
