---
work_package_id: WP03
title: Wire the authority into consolidate
dependencies:
- WP01
- WP02
- WP06
requirement_refs:
- FR-005
- FR-006
- FR-010
- FR-011
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-5686-rollback-anchor
merge_target_branch: issue-5686-rollback-anchor
branch_strategy: Planning artifacts for this mission were generated on issue-5686-rollback-anchor. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5686-rollback-anchor unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-rollback-anchor-authority-01M45VSA
base_commit: 22fb364234b934d77b1efba895bd1dc5e3d1c9bb
created_at: '2026-10-05T12:49:44.086001+00:00'
subtasks:
- T012
- T013
- T014
- T015
phase: Phase 2 - Wiring
history:
- at: '2026-10-05T12:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/run_state.py
create_intent:
- tests/consolidation/test_rollback_anchor_kill_window.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/run_state.py
- src/specify_cli/consolidation/executor.py
- src/specify_cli/consolidation/phase_claim.py
- tests/consolidation/test_executor_rollback_wiring.py
- tests/consolidation/test_rollback_anchor_kill_window.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Wire the authority into consolidate

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill (or `spec-kitty agent profile show python-pedro`) to load the agent profile in the frontmatter, and follow its guidance before you read the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

Also run `spec-kitty charter context --action implement --json` and apply it.

---

## Objectives & Success Criteria

WP02 made `consolidation/rollback.py` anchor every restore on the persisted record. WP06 gave `git/ref_advance.py` an advance-intent sink and a lagging-checkout restore. WP01 retired the second restore path. This WP connects them in the consolidate run:

1. **Advance intents (FR-006).** `executor._run_lane_based_consolidation_locked` installs `ref_advance.reporting_advance_intents(sink)` around the door `try` (the post-mutation span) only. The sink persists each report with `rollback.note_advance_intent`. A persist failure propagates, so the advance never happens.
2. **Recorder taint (FR-011).** `run_state._records_post_mutation_tips` captures, at phase entry, each run-movable branch's live tip L0 and the tip the record expected, E0 (the recorded post tip, else the restore target).
   - At phase exit it records a branch only if `L != L0 and L0 == E0`.
   - For every branch that moved during the phase, whether recorded or rejected, it clears that branch's intents with `rollback.clear_advance_intents`, then saves.
   - Expectations are per recorder instance, so nested recorders (e.g. `coord_strand._restore_and_guard_coord_coherence` inside recorded phases) never taint the outer phase.
   - Expose the rule as a small pure helper and unit-test it.
3. **Early refusal (FR-005).** Before `_record_operator_attestations` and before `_heal_pending_coord_reconcile`:
   - If a record with a snapshot already exists for this mission (`load_state`, read-only; skip when absent), call `rollback.unexplained_branches`.
   - On a non-empty result, refuse with `UNEXPLAINED_BRANCH_MOVE` (exit 1). The message ends `Error code: UNEXPLAINED_BRANCH_MOVE.` It names each branch, its restore target and its live SHA, says that nothing was changed and the record is kept, and gives exactly the non-destructive remedies in `data-model.md`. No `reset --hard`, `branch -f` or `update-ref` text (C-002).
   - Then capture this process's start tips (`rollback.movable_branch_tips`) into a new `_MergeRunState` field, and pass them to `begin_attempt(own_moves=...)` in `phase_claim._capture_snapshot_and_begin_attempt`. That function also refuses identically on a non-empty return.
4. **PASS settles the target, only once the door span completed (post-tasks squad HIGH).** After the door `try` returns normally (the reconciliation PASS and the squash projection proof both succeeded), call `rollback.settle_branch(main_repo, state, target)` in `executor.py`. Do NOT settle inside `phase_gate._record_reconciliation_pass`: the projection proof can still refuse after it. On the `_resume_reconciliation_already_passed` short-circuit path, settle the same way once the span completes.
5. **P0 marker:** remove `@pytest.mark.p0_repro(issue=5686)` from `tests/consolidation/test_rollback_anchor_p0_repro.py`. This is a one-line leeway edit in a WP01-owned file; the lanes have consolidated by now. SC-001: the file passes with and without `SPEC_KITTY_RUN_P0_REPRO=1`.

Done when every scenario below has a production-path test (in-process terminus harness, or a subprocess for kills) with a positive control on the same fixture builder, and these existing suites are green: `tests/terminus/test_resume_recovers_lagging_checkouts.py`, `tests/terminus/test_abort_restores_snapshot.py`, `tests/terminus/test_rollback_restores_refs.py`, `tests/terminus/test_rollback_door.py`, `tests/consolidation/test_single_rollback_authority.py`.

## Orchestrator ruling: the coord-strand heal is a sanctioned recovery (from the WP02 hand-off)

`tests/consolidation/test_issue_2786_revert_failure_split_brain.py::test_unrestorable_coordination_branch_keeps_the_marker_and_the_resume_heals` passes on the base. It fails once WP02 lands without this WP.

The scenario:
- A door rollback left the coordination branch NOT restored: another actor committed on top of this run's stranded `done` commit.
- The record carries a `pending_coord_reconcile` marker naming that branch.
- The resume-start heal (`_heal_pending_coord_reconcile` → `repair_coord_strand`) reverts the stranded `done` forward. Nothing of this run's then remains under the foreign commit.

Implement it this way:
- **Pre-check:** skip the branch named by `pending_coord_reconcile["coord_ref"]` while that marker is present. The heal owns it.
- **After the heal:** if the heal cleared the marker (healed, or re-derived coherent), call `rollback.settle_branch(main_repo, state, coord_ref)` and take the process start tip of that branch after the heal. `begin_attempt` then applies the settled-branch A2 rule (re-anchor to the live tip, keep the foreign commit), which is the pre-existing behaviour the test pins.
- **If the heal could not clear the marker:** the branch stays unsettled, and `begin_attempt` (with `own_moves`) refuses with `UNEXPLAINED_BRANCH_MOVE`.

Keep that test green and unchanged. Add one test for the heal-failed refusal. Record this ruling as a residual for WP05's ADR text: the heal is trusted to remove this run's only content on the coordination branch.

## Carried from the WP02 review (LOW, fold here)

- `rollback.settle_branch` does not drop the branch's intent chain (`_settle_outcomes` does). Make it pop the chain. This is a leeway edit in `rollback.py`; record it. Without that, a stale chain stays behind after the PASS settle.
- Add a partial-rollback test: the settled branch's chain is gone, and a NOT_RESTORED branch's chain stays (`rollback.py` `_settle_outcomes` intent pop; a mutant removing it currently survives).
- The recorder must clear each branch's chain when it records. Otherwise the next `note_advance_intent` extends a chain with a stale base, and that chain can never be adopted.

## Context & Constraints

- Read `spec.md`, `data-model.md` and `research/code-grounding.md` §2 and §7.
- AST door pin (`test_single_rollback_authority.py` rule 3): every span phase call stays inside the ONE door `try`. A `with` around the `try` is fine (the scan uses `ast.walk`). Check it.
- Known in-span moves that never report an intent: `consolidation/mission_number/bake.py:389` (plain commit) and the plain `safe_commit` path (`commit_helpers.py:869`). A kill right after one of them is unexplained, which fails closed by design. List them in the activity log for WP05's ADR residuals, and test one.
- Charter: red-first per subtask (commit the failing tests first); complexity ≤ 15; mypy clean; C-002; do not edit `reconciliation.py` (C-003) or the coord status-write seam (C-004).

## Branch Strategy

- **Strategy**: lanes. Use the workspace `spec-kitty implement WP03` prints.
- **Planning base / merge target**: `issue-5686-rollback-anchor`

## Subtasks

### T012 – Recorder taint and intent clearing (objective 2)

Tests in `tests/consolidation/test_executor_rollback_wiring.py`:
- A foreign commit lands between two recorded phases, and the next phase commits on top of it. That branch is not recorded, its intents are cleared, and the door reports NOT_RESTORED with the foreign commit kept.
- Nested recorders do not taint.
- `test_persisted_post_tips_equal_live_tips_after_every_real_phase` stays green.

### T013 – Executor pre-check, sink installation, own moves (objectives 1 and 3)

### T014 – PASS settles the target after the door span (objective 4)

Test: after a successful run whose push is then rejected (or after a forced post-span failure such as `_phase_push` raising), the record keeps the target settled. A `--resume` is not refused for the target, nor for mission or coord branches that sit at their recorded post tips.

### T015 – Scenarios in `tests/consolidation/test_rollback_anchor_kill_window.py` (+ the P0 marker removal)

1. **US2 AS1: kill after `update-ref` of the target, before the resync.** Run consolidate in a **subprocess** (`sys.executable -c` with a tiny runner) on a real lanes fixture. Reuse `tests/terminus/lanes_fixture.py` if it builds in `tmp_path`; otherwise build it through the CLI. Monkeypatch `specify_cli.git.ref_advance._resync_checkouts` to `os._exit(137)` when `branch` is the target. Then run `consolidate --abort` and assert:
   - exit 0;
   - the target is at its pre-run tip;
   - the output has a `restored ... (adopted interrupted advance)` line;
   - the repository root checkout is clean;
   - the record is cleared.
2. **Variant:** the kill happens right after `advance_branch_ref` returns for the target. Same assertions.
3. **US2 AS2/AS3, same fixture builder, unprovable.**
   - Setup: kill after the advance, then remove that branch's chain from `advance_intents` in `state.json` (equivalent to a commit-based move).
   - A re-run refuses with `UNEXPLAINED_BRANCH_MOVE`, exit 1, and the record is byte-identical.
   - A second re-run refuses identically.
   - `--abort` reports NOT restored, exits 1 and keeps the record. Running it again gives the same result.
   - Assert that no refusal text contains `reset --hard`, `branch -f` or `update-ref` (C-002).
4. **The refusal precedes the attestations and the heal.** In the same unprovable state, re-run with `--attest-canceled-superseded <WP> --attest-reason x` (on a fixture with a canceled WP). With a `pending_coord_reconcile` marker present, assert that no status event was appended and no revert commit was created.
5. **US4 AS2: an orderly exit does not settle.**
   - A FAIL with a foreign commit (WP01's door fixture) leaves the target NOT_RESTORED.
   - A re-run then refuses with `UNEXPLAINED_BRANCH_MOVE`, and `--abort` keeps the record.
6. **US1 AS2: foreign interleave between phases.** Use the in-process terminus harness. Wrap `_phase_commit_and_assert` (or `_phase_record_done_and_project`) so that a foreign commit lands on the target first, then call the original and force a gate FAIL. The foreign commit stays reachable, and the report says NOT restored.
7. **Positive control:** the same fixture with no kill and no foreign commit consolidates successfully.

Use the markers the suite already uses (`git_repo`, `integration`). Keep the runtime reasonable.

## Test Strategy

```bash
uv run --frozen pytest tests/consolidation tests/terminus tests/git -q -n auto --dist loadfile
uv run --frozen pytest tests/specify_cli/cli/commands/test_consolidate_abort_rollback.py -q
uv run --frozen pytest tests/integration -k "consolidat or merge or abort or resume" -q -n auto --dist loadfile
SPEC_KITTY_RUN_P0_REPRO=1 uv run --frozen pytest tests/consolidation/test_rollback_anchor_p0_repro.py -q -n0
uv run --frozen pytest tests/architectural/test_layer_rules.py tests/architectural/test_destructive_op_routing.py -q
make test-fast
uv run --frozen ruff check <changed> && uv run --frozen ruff format --check --force-exclude <changed>
uv run --frozen mypy <changed src files>
```

## Risks & Mitigations

- Any undecorated code that moves a run-movable branch between recorded phases now taints the next phase. The real-phase wiring test catches this. If you find a legitimate undecorated mover, decorate it or report it. Do not weaken the taint rule.
- Subprocess tests must not depend on the user's HOME.

## Review Guidance

- Every scenario uses the production path and has a same-fixture positive control.
- The layering and door pins are green.
- No restore path added.

## Activity Log

- 2026-10-05T12:00:00Z – system – Prompt created.
- 2026-10-05T12:30:00Z – system – Revised after the post-tasks squad: T011 split into WP06; PASS settle moved to executor; marker removal and named suites added.
- 2026-10-05T14:05:10Z – claude – shell_pid=16753 – Red-first d9884d0e (tests only; src stashed so the run used lane HEAD c00bf632): uv run --frozen pytest tests/consolidation/test_rollback_anchor_kill_window.py tests/consolidation/test_executor_rollback_wiring.py -n auto --dist loadfile -> 25 failed, 43 passed. Red per subtask: T012 phase_records_branch rule x5, foreign-interleave-under-next-commit, recorder clears chain; T013 precheck x4, claim refusal + own-move, door intent sink x2; T014 settle_branch spends chain, PASS-settle-then-resume; T015 kill-window adopt x2 (no intent persisted), unprovable, refusal-precedes-attestations-and-heal, orderly FAIL, between-phases interleave, heal-failed refusal, intentless plain commit. Guards green on base by design: nested recorders, unmoved chain kept, partial-rollback chain pop (pins WP02 _settle_outcomes), projection-refusal-does-not-settle, positive control.
- 2026-10-05T14:05:13Z – claude – shell_pid=16753 – Green acf216e0: run_state recorder captures entry tips + rollback.expected_tips per recorder instance and records only phase_records_branch(entry, expected, live) (L!=L0 and L0==E0); every moved branch's chain cleared. executor: read-only _refuse_unexplained_branch_moves before _record_operator_attestations (skips the pending_coord_reconcile branch; exempt when the PASS still holds for the live target tip, FR-011/#5021/#5570), process_start_tips -> _MergeRunState -> begin_attempt(own_moves=) in phase_claim with the identical refusal (_exit_unexplained_branch_move, phase_claim); heal that cleared its marker -> settle_branch(coord) + post-heal start tip (ruling); reporting_advance_intents(sink->note_advance_intent) around the door try only; settle target after the door span (both paths). Mutation checks: dropping L0==E0 turns both interleave tests red; disabling both refusals turns 4 scenario tests red.
- 2026-10-05T14:05:16Z – claude – shell_pid=16753 – Leeway edits: rollback.py (settle_branch pops the intent chain [WP02 review LOW]; expected_tips + phase_records_branch; record_post_mutation_tips(expected_tips=) clears moved chains); tests/consolidation/test_rollback_anchor_p0_repro.py (p0_repro marker removed, docstring updated); cb9a51ae re-pins: test_resume_refuses_committed_staged_deletions (APPROVED_CONTENT_MISSING -> earlier UNEXPLAINED_BRANCH_MOVE naming the mission branch, US2 AS2) and test_coord_teardown_cas_branch_delete::test_5570_a_foreign_target_commit_is_never_stamped_verified ('Reconciliation refused' -> UNEXPLAINED_BRANCH_MOVE naming the coord branch). Both still refuse, move nothing. test_issue_2786 green UNCHANGED. Console renderer lives in phase_claim (run_state is not in the cli.console importer ledger).
- 2026-10-05T14:05:19Z – claude – shell_pid=16753 – Tests: consolidation+terminus+git -n auto --dist loadfile -> 2231 passed, 4 failed, 3 skipped, 5 xfailed. Reds classified: test_protection_config_honoring x2 red on base 22fb3642 (pre-existing); test_resume_recovers_lagging_checkouts [lock_coord] + index-lock control red on lane HEAD c00bf632 BEFORE WP03 and green on base -> introduced by the WP06/WP02 merges: the door's restore_branch_ref now accepts the lagging coord checkout (FR-012), CAS-moves the ref back, then the resync reset --hard fails on the planted index.lock and _restore_one reports NOT_RESTORED though the ref was restored; the fixture precondition (mission ref still advanced) no longer holds. Not fixed here (ref_advance/rollback._restore_one are WP06/WP02 surfaces). test_consolidate_abort_rollback 18 passed; p0 repro 2 passed with and without SPEC_KITTY_RUN_P0_REPRO=1; layer_rules+destructive_op_routing 107 passed; integration -k consolidat/merge/abort/resume 93 passed, 1 failed (#5651 baseline), 1 skipped; make test-fast 2279 passed, 8 skipped. ruff/format clean; mypy: only the 2 pre-existing no-any-return in rollback.py (_record_restore_target/_effective_post, same as lane HEAD); C901 clean.
- 2026-10-05T14:05:23Z – claude – shell_pid=16753 – Residuals for WP05 ADR: (1) in-span moves with no intent: plain safe_commit (commit_helpers._run_commit_capture_sha, e.g. LANES done bookkeeping + bookkeeping commit on the target) and mission_number/bake.py primary-tree git commit; a kill right after one is unprovable -> UNEXPLAINED_BRANCH_MOVE (tested: plain safe_commit). (2) Ruling: the coord-strand heal is trusted to remove this run's only content on the coordination branch; a heal that cleared its marker settles that branch. (3) Post-PASS own moves outside the span (teardown retrospective/bookkeeping commits on the coordination branch) are not recorded; if the target then moves so the PASS no longer holds, a resume refuses UNEXPLAINED_BRANCH_MOVE (seen in the re-pinned #5570 foreign-target test). (4) The killed run's global merge lock is not reclaimed; a re-run first needs the lock removed (MergeLockError), as before.
- 2026-10-05T14:41:53Z – claude – shell_pid=16753 – Orchestrator rulings round. Red c81a6d96: test_restore_branch_ref_resync::test_restore_over_a_lagging_checkout_never_resets_it_even_with_a_live_index_lock FAILED (RefResyncError on the planted index.lock; positive control passed); wiring test_precheck/claim_exempts_only_the_target_of_a_verified_landing 2 FAILED. Green c0947be0 + 92849fad: 75 passed (both files).
- 2026-10-05T14:41:57Z – claude – shell_pid=16753 – Leeway c0947be0 (git/ref_advance.py): restore_branch_ref(resync_checkouts=True) no longer hands _resync_checkouts a checkout whose index+worktree already equal restored_sha (HEAD is a symref; the CAS alone makes it consistent). advance_branch_ref untouched. Re-pin (approved_content_support.py, lock arm only, kill arms untouched): the surviving lock-arm run's door now restores the mission branch truthfully (RESTORED line, ref at snapshot, clean checkout, planted index.lock untouched) instead of leaving a lag, so the old 'ref advanced + staged deletions' precondition cannot hold. test_5571_resume_recovers_a_pure_lag...[lock_coord] assertions unchanged (resume after removing the lock: rc 0, all approved code lands, no 'Commit'). The live-index.lock control's assertions are unchanged and still pass: the resume refuses rc 1 naming index.lock (its own lane-merge resync fails, the door restores again), no 'Commit', nothing lands.
- 2026-10-05T14:42:00Z – claude – shell_pid=16753 – 92849fad (ruling 2): the FR-011 exemption now covers only the target while it sits at the PASS anchor. CONFLICT, reported and not re-pinned: test_coord_teardown_cas_branch_delete::test_5570_printed_recovery_advice_reaches_an_honest_end_state and ::test_5570_coordination_branch_moving_again_after_the_late_projection_refuses_again go red. After a verified landing, the coordination branch moved after the landing (#5570 COORD_MOVED_AFTER_LANDING), and the documented remedy 'consolidate --resume finishes the teardown' now refuses with UNEXPLAINED_BRANCH_MOVE naming the coordination branch. Both passed with the whole-check exemption (acf216e0).
- 2026-10-05T14:42:03Z – claude – shell_pid=16753 – Tests after the rulings: consolidation+terminus+git -> 2235 passed, 4 failed, 3 skipped, 5 xfailed. Reds: test_protection_config_honoring x2 (red on base 22fb3642) and the 2 #5570 tests above (caused by ruling 2). The lock_coord pair is green. test_consolidate_abort_rollback 18 passed; P0 repro 2 passed with and without the env var; layer_rules+destructive_op_routing 107 passed; integration subset 93 passed, 1 failed (#5651 baseline), 1 skipped; make test-fast 2279 passed, 8 skipped. ruff/format clean; mypy only the 2 errors already in rollback.py.
- 2026-10-05T15:05:59Z – claude – shell_pid=16753 – Orchestrator decision option (a), a7f2a0df: reverted the 92849fad narrowing. While the live target equals the PASS anchor (reconciliation_passed_for_tip), the pre-check and the claim refuse no branch. Rationale: under FR-011 rollback_to_snapshot refuses any rollback while the PASS holds, begin_attempt writes nothing for an unexplained branch, and the teardown deletes are compare-and-swap protected, so the documented #5570 --resume cannot discard the coordination commit; refusing would only force a needless --release-branch. Re-pinned the c81a6d96 narrowing tests to this rule (pre-check and claim, each with a positive and a negative case): target at the anchor + unexplained mission move -> no refusal, record unchanged; target moved off the anchor -> UNEXPLAINED_BRANCH_MOVE. Both #5570 tests are green and unchanged. Suites: consolidation+terminus+git 2239 passed, 2 failed (test_protection_config_honoring x2, red on base 22fb3642), 3 skipped, 5 xfailed; abort 18; P0 repro 2+2; layer/destructive gates 107; integration 93 passed, 1 failed (#5651 baseline), 1 skipped; make test-fast 2279 passed, 8 skipped; mypy only the 2 errors already in rollback.py.
