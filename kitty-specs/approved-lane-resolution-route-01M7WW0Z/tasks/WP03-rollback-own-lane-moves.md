---
work_package_id: WP03
title: Rollback undoes the run's own auto-rebase lane moves
dependencies:
- WP02
- WP07
requirement_refs:
- FR-009
- NFR-002
- C-006
planning_base_branch: fix/approved-lane-resolution-route
merge_target_branch: fix/approved-lane-resolution-route
branch_strategy: Planning artifacts for this mission were generated on fix/approved-lane-resolution-route. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/approved-lane-resolution-route unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-approved-lane-resolution-route-01M7WW0Z
base_commit: b61f303b619e61b5d05dcaf0f804b202b895cff8
created_at: '2026-11-25T17:36:24.625900+00:00'
subtasks:
- T018
- T019
- T020
- T021
- T022
phase: Phase 2 - Behaviour
history:
- at: '2026-11-20T17:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- tests/consolidation/test_rollback_own_lane_moves.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/rollback.py
- src/specify_cli/consolidation/state.py
- tests/consolidation/test_rollback_authority.py
- tests/consolidation/test_rollback_own_lane_moves.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 - Rollback undoes the run's own auto-rebase lane moves

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission approved-lane-resolution-route-01M7WW0Z`).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: as you address each item, record it with `spec-kitty agent tasks add-history WP03 --note "..."`.

---

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

Today a consolidate run that auto-rebases a stale lane and then fails leaves the auto-rebase merge on the lane. The single rollback authority treats every lane as report-only:

- guarantee 2a, `src/specify_cli/consolidation/rollback.py:20-23`: "consolidation never moves a lane branch";
- `_rollback_branch` returns `UNCHANGED_BY_RUN` for every snapshotted lane, `rollback.py:999-1000`;
- ADR `docs/adr/3.x/2026-09-19-1-*` Decision A2 says the same.

That premise is false: `phase_advance._record_own_auto_rebase` (`consolidation/phase_advance.py:198-210`) already records this run's own lane move in `ConsolidationState.lane_rebase_moves` (`state.py:350-356`) as `[before, after]`.

This WP makes the rollback undo exactly that move and nothing else:

- for each lane with a `lane_rebase_moves` entry `[before, after]` whose `before` is the lane's restore target and whose live tip is `after`: compare-and-swap `after -> before`, resync the lane checkout, reset the lane work-tip ref, delete the auto-rebase record (WP02);
- a lane whose live tip is no longer `after` is reported with the new outcome `LANE_MOVED_SINCE_AUTO_REBASE`: not restored, record kept, report not re-baselineable;
- every other lane move stays report-only (`UNCHANGED_BY_RUN`), including a lane named in `post_mutation_refs` (a legacy record).

Done when:

- the red reproduction (T018) shows the harm at HEAD and is green after the change;
- the two pinned report-only tests are re-pinned to the narrow rule, and a non-recorded lane move is still report-only;
- `tests/consolidation/test_single_rollback_authority.py` stays green (the restore lives only in `rollback.py`);
- ruff, `ruff format --check --force-exclude` and mypy are clean on every changed file; complexity <= 15; no suppressions.

## Context & Constraints

- Read first: `spec.md` (US6, FR-009, NFR-002, SC-004), `plan.md` (IC-02), `research.md` (R-05), `data-model.md` ("ConsolidationState.lane_rebase_moves"), `contracts/refusal-codes.md` ("Rollback outcome LANE_MOVED_SINCE_AUTO_REBASE"), `squads/01-pre-spec-and-post-specify.md` (squad 2: FR-009 rows), and ADR `docs/adr/3.x/2026-09-19-1-*.md` (A2, A3, residuals). WP13 amends that ADR; you only implement.
- Charter: `.kittify/charter/charter.md`; `spec-kitty charter context --action implement`.
- Integrity invariants:
  - **C-006 / single rollback authority**: the lane restore lives in `consolidation/rollback.py` only. `tests/consolidation/test_single_rollback_authority.py` (rule 2, `:284-298`) fails on any `restore_branch_ref(..., resync_checkouts=True)` outside `rollback.py`. Do not add a second restore path anywhere (not in `phase_advance`, not in `lanes/`).
  - **CAS only**: the restore uses `git.ref_advance.restore_branch_ref(repo_root, branch, before, expected_current_sha=after, resync_checkouts=True, context=...)` (`git/ref_advance.py:837-897`). Never a raw `reset --hard` or `update-ref` (`tests/architectural/test_merge_pipeline_ratchets.py` AC-B3).
  - **Narrow source**: the ONLY restore source for a lane is `state.lane_rebase_moves`. `post_mutation_refs` never makes a lane restorable (the existing pin `test_lane_branches_are_report_only_even_with_a_recorded_post_tip`, `tests/consolidation/test_rollback_authority.py:362-376`, keeps that assertion).
  - **Fail closed** (NFR-002): a lane that cannot be restored (moved, dirty checkout, CAS refused) is never reset by force; it is reported and its record is kept.
  - **C-002**: no new release or override for lanes. `release_branch` stays for run-movable branches only.
  - Never loosen the resume lane-tip CAS (`state.lane_tip_cas_ok`, `state.py:995-1040`) to make SC-004 pass (anti-fake check, below).
- **Dependencies**:
  - WP02 provides `lanes/auto_rebase_record.delete(repo_root, lane_branch, merge_sha)`.
  - WP07 records `lane_rebase_moves` on EVERY auto-rebase merge, not only when the lane later consolidated (`phase_advance.py:420-422` today). WP07 is a hard dependency, so it is in your base when you start: the "lane consolidation failed after the auto-rebase" shape (T018 test 4) is MANDATORY, not optional.
- Terminology: Mission; lane consolidation; never "sync".

## Branch Strategy

- **Strategy**: populated by `finalize-tasks`
- **Planning base branch**: `fix/approved-lane-resolution-route`
- **Merge target branch**: `fix/approved-lane-resolution-route`

> These fields are populated automatically by `spec-kitty agent mission finalize-tasks`.
> Do NOT change them manually unless you are certain the branch topology has changed.

Implement command:
`spec-kitty agent action implement WP03 --agent claude --mission approved-lane-resolution-route-01M7WW0Z`

## Subtasks & Detailed Guidance

### Subtask T018 - Red reproduction of the observed harm at the base

- **Purpose**: squad 2 (architect F4) showed the issue's `--resume` symptom may not reproduce: the resume lane-tip CAS accepts a descendant (`state.lane_tip_cas_ok`), and the re-baseline drops `pre_interrupt_lane_tips` on LANES and SINGLE_BRANCH (`rollback.py:1106-1109`). So this WP is red-first on what DOES happen, and records the actual code.
- **File**: `tests/consolidation/test_rollback_own_lane_moves.py` (new). Markers: `pytest.mark.integration`, `pytest.mark.git_repo`.
- **Fixture**: a real Mission where the second lane goes stale when the first lands, AND whose lane worktrees exist, so the auto-rebase actually runs.
  - **Do NOT use `tests/terminus/conftest.py::build_coord_mission_shared_file`** (`:836`): it cuts lane branches with `_cut_lane_branch` (`:599`) and allocates no lane worktree. `lanes/consolidation._try_auto_rebase_if_stale` returns the stale result unchanged when the worktree is missing (`lanes/consolidation.py:239-240`), so no auto-rebase runs and no `lane_rebase_moves` entry is written; `tests/terminus/test_repro_5051_clean_3way.py:136-140` shows that builder's first run stopping at the stale-lane refusal.
  - **Use a builder that calls the real `allocate_lane_worktree`**: the `tests/terminus/post_approval_support.py` builders do (`build_post_approval_lanes_mission`, `:109-151`, calls `allocate_lane_worktree` at `:143`; the coord builder delegates to `canceled_dependency_support.build_canceled_dependency_mission`). That module is FROZEN (its docstring, `:34-35`), so extend it LOCALLY: write `_build_shared_file_mission(tmp_path)` in `test_rollback_own_lane_moves.py`, modelled on `build_post_approval_lanes_mission` (copy its body; import only its public names and `canceled_dependency_support`'s `ACTOR`, `_commit_in`, `_approve`), with one change: seed `src/pkg/shared.py` (about 20 lines) on the target before the Mission branch and the lanes are cut, and have WP01 (lane-a) and WP02 (lane-b) both edit that file in DISJOINT, non-adjacent regions (for example line 2 and line 18). Both WPs are approved through the production shell, so their stamps come from `read_lane_head`.
  - **Builder preconditions** (asserted inside the builder): both lane worktrees exist; `git merge-tree --write-tree <lane-a> <lane-b>` exits 0 (the CLEAN shape); both lanes changed `src/pkg/shared.py`; each WP's newest approval stamp equals its lane tip.
  - **AUTO-RESOLVED shape** (a merge with content of its own; used for tests 1 and 3 only): the same local builder with an additive `pyproject.toml` dependency edit on both lanes (the classifier's additive rule, `tests/lanes/test_auto_rebase_additive.py:188`).
  Drive the real executor in-process exactly as `tests/terminus/test_rollback_record_rebaseline.py:69-80` does (`executor._run_lane_based_consolidation`), and make the REAL gate FAIL once with the one-shot wrapper pattern of `:83-101` (first `MergeOutcomeVerifier.verify` call returns a FAIL, later calls delegate).
- **Tests (post-fix expectations; red at HEAD)**:
  1. `test_a_failed_run_restores_the_auto_rebased_lane`: after the failed run, `lane-b`'s tip equals its pre-run tip (read before the run), the report line for `lane-b` says `restored`, `refs/spec-kitty/lane-tip/<lane-b>` equals the pre-run tip, and no `refs/spec-kitty/auto-rebase/<lane-b>/` ref is left. At HEAD the lane tip is the merge (red).
  2. `test_the_next_run_is_not_harmed_by_the_run_s_own_merge` (**CLEAN shape only**): after the failed run, a second, real (unpatched) run of the same Mission exits 0, and no refusal or FAIL text of that second run names any commit of the first run's recorded lane move (read `[before, after]` for lane-b from the persisted `lane_rebase_moves` after the first run, BEFORE the rollback drops it; assert neither `after` nor its SHA12/SHA7 appears in the second run's output). Not on the auto-resolved shape: its own content is never reached by an approval stamp, so the gate still judges it (spec US3 AS3) and exit 0 cannot hold there. There is no fallback assertion: "the output does not name `<merge>`" alone always passes, because the second run makes a NEW auto-rebase merge with a new SHA. Run it on HEAD first and write the observed outcome into WP history: `spec-kitty agent tasks add-history WP03 --note "T018 red at HEAD: clean shape -> <exit code> <code or verdict text>"`.
  3. `test_the_lane_checkout_is_resynced`: the lane worktree's `HEAD`, index and working tree all equal the restored tip (no staged reversal of the merge left behind, the #4997 / `APPROVED_CONTENT_MISSING` trap squad 2 named).
  4. `test_a_lane_whose_consolidation_failed_after_the_auto_rebase_is_restored` (MANDATORY; needs WP07's record-on-every-move, which is in your base): the auto-rebase of lane-b succeeds, then lane-b's consolidation into the Mission branch fails (inject one failure into `lanes.consolidation._merge_branch_into`, `lanes/consolidation.py:1403`, with a one-shot monkeypatch that raises `RuntimeError` on its first call for lane-b and delegates afterwards). Assert the record names lane-b with `[pre tip, <merge>]` (WP07 records it although the lane did not consolidate), and after the rollback lane-b's tip, lane-tip ref and checkout equal the pre-run tip and no auto-rebase ref is left for lane-b.
- **Steps**:
  1. Build the Mission; read and keep `pre = {lane-b tip, lane-b lane-tip ref, mission tip, target tip}` before the run.
  2. Install the one-shot FAIL wrapper; run the executor in-process; assert it exits non-zero (fixture precondition: the run must reach the gate, so assert the gate was called once).
  3. Assert the auto-rebase really happened in that run: the persisted record's `lane_rebase_moves` names lane-b with `[pre lane-b tip, <merge>]` and `<merge>` has two parents. Without this precondition test 1 could pass on a fixture where nothing went stale.
  4. Assert the post-fix expectations (tests 1, 3 and 4).
  5. For test 2 (clean shape), remove the wrapper and run again; assert exit 0 and that no commit of the first run's recorded move is named. No other outcome is accepted.
- **Why red at HEAD**: `_rollback_branch` returns `UNCHANGED_BY_RUN` for lane-b (`rollback.py:999-1000`), so the merge stays on the lane, the lane checkout keeps it and the lane-tip ref still names it (`auto_rebase.py:981-984`).
- **Files**: `tests/consolidation/test_rollback_own_lane_moves.py` (imports `tests.terminus.conftest` builders and `tests.terminus.rollback_harness` helpers, as `tests/consolidation/characterization_support.py` already does).
- **If test 2 is green at HEAD on the clean shape**: keep tests 1, 3 and 4 as the red-first proof (they are red at HEAD by construction), keep test 2 as a ratchet labelled as such in history. Do not invent a harm and do not weaken its assertion.
- **Validation**: four tests, red at HEAD with the recorded outcome (test 2 possibly a ratchet, see above); green after T020-T022.
- **Edge cases**:
  - a lane whose worktree is absent: the auto-rebase does not run (`lanes/consolidation._try_auto_rebase_if_stale`, `:238-240`), so there is no move and nothing to restore; add no test here (WP07 covers the halt reason);
  - a coordination topology versus LANES: run test 1 on the builder's default topology; note which one in history.
- **Parallel?**: no; it opens the WP.

### Subtask T019 - Re-pin the two report-only tests; keep non-recorded moves report-only

- **Purpose**: the pinned tests encode the broad rule ("a lane is never restored"). Re-pin them to the narrow rule deliberately; never delete them (Standing Order 5, `delete-the-assertion-not-the-test`).
- **File**: `tests/consolidation/test_rollback_authority.py`.
- **Steps**:
  1. `test_lane_branches_are_report_only_even_with_a_recorded_post_tip` (`:362-376`): keep every assertion about `post_mutation_refs` (a legacy record naming the lane still does not make it restorable). Change only the rendered reason it asserts (`"lane branch: not moved by consolidation"`, `:376`) to the new narrow reason constant (T020), and rename the test to `test_a_lane_named_only_in_post_mutation_refs_is_report_only`. Update its docstring: consolidation moves a lane only through its own recorded auto-rebase.
  2. `test_record_never_records_a_lane_branch` (`:379-386`): still true (lane moves are never recorded as post tips). Keep it; add one sentence to its docstring that the lane's own move lives in `lane_rebase_moves`, not in `post_mutation_refs`.
  3. Add `test_a_lane_moved_by_a_commit_that_is_not_the_run_s_auto_rebase_is_report_only`: a lane with NO `lane_rebase_moves` entry and a foreign commit -> `UNCHANGED_BY_RUN`, tip unchanged.
  4. Add `test_a_recorded_move_from_another_tip_is_report_only`: `lane_rebase_moves[lane] = [X, after]` where `X` is not the lane's restore target -> `UNCHANGED_BY_RUN` (a move recorded by an earlier attempt whose snapshot was re-captured is not this attempt's; mirrors `lane_cleanup.cleanup_expected_tips`, `lane_cleanup.py:239-249`).
  5. Add `test_a_recorded_move_is_restored`: `lane_rebase_moves[lane] = [snapshot, after]` with the lane at `after` -> `RESTORED`, tip == snapshot.
  6. Extend the truth table `test_rebaselineable_is_stricter_than_fully_restored_for_kept_and_missing_branches` (`:1199-1217`) with `((RESTORED, LANE_MOVED_SINCE_AUTO_REBASE), False)` and assert `fully_restored is True` for it (T021 decision).
- **Fixture**: reuse the module's own `make_env`, `_snapshot_and_begin`, `_advance_run`, `_commit_on` (`:114-146`). Build `after` as a real two-parent merge with `git commit-tree <tree> -p <lane> -p <mission>` and move the lane with a plain test-local `git update-ref` (tests may use raw git; the AC-B3 ratchet scans `src/` only).
- **Validation**: steps 3-5 are red at HEAD only for step 5 (steps 3 and 4 pass at HEAD and stay green: they are the controls that keep the narrow rule narrow). Record that in history.
- **Edge cases**: the lane's `restore_to` comes from `state.restore_targets.get(branch, snapshot)` (`rollback.py:996`), which `begin_attempt` sets for lanes too (`_lane_attempt_start`, `:699-703`). Write step 4 against that restore target, not against the raw snapshot.
- **Why re-pin and not delete**: those two tests are the only pins of ADR 2026-09-19-1 A2 at the code level. After this WP, A2 still holds for every lane move except one; the tests must keep proving that "except one" is exactly one. A deleted test would leave the broad rule unguarded the next time someone widens the restore.
- **Other pins that must keep passing unchanged**:
  - `test_operator_fix_without_attempt_in_flight_is_unchanged_by_run` (`:347-359`): a lane commit after a full restore is still `UNCHANGED_BY_RUN`;
  - `test_four_lane_rollback_is_fast` (`:658-688`): every lane `UNCHANGED_BY_RUN` when nothing was auto-rebased (and the extra dict lookup costs nothing);
  - `test_executor_rollback_wiring.py:189` accepts `NOT_RESTORED` or `UNCHANGED_BY_RUN` for its lane; check it still holds.
- **Files**: `tests/consolidation/test_rollback_authority.py`.
- **Parallel?**: yes with T018 (different files).

### Subtask T020 - Implement the lane restore in `rollback.py`

- **Purpose**: one narrow branch inside the existing authority.
- **Steps**:
  1. In `_rollback_branch` (`rollback.py:992-1007`), replace the lane early return at `:999-1000` with a call to a new helper `_rollback_lane(repo_root, state, branch, snapshot, restore_to, live, context) -> BranchOutcome`. The checks above it (missing branch `:994-995`, already at target `:997-998`) stay first and unchanged.
  2. `_rollback_lane`:
     - `move = state.lane_rebase_moves.get(branch)`; when it is missing, malformed (not exactly two SHAs) or `move[0] != restore_to`: return `UNCHANGED_BY_RUN` with the narrow reason (rename `_LANE_REPORT_ONLY_REASON`, `:134`, to `"lane branch: no auto-rebase move of this run recorded"`).
     - `before, after = move`; when `live != after`: return the new `LANE_MOVED_SINCE_AUTO_REBASE` outcome (T021) with `expected_sha=after`, `restored_to_sha=before`, `observed_sha=live`.
     - otherwise: `outcome = _restore_one(repo_root, branch, snapshot, before, live, after, adopted=False, context=context)` (`:948-981`). It already maps a dirty lane checkout to `NOT_RESTORED`/`DIRTY_CHECKOUT` and a refused CAS to `NOT_RESTORED`/`RESTORE_REFUSED`, and `restore_branch_ref(..., resync_checkouts=True)` already resyncs every checkout of the branch (`git/ref_advance.py:853-866`). So you do NOT call `resync_checkouts_to_tip` separately (the tasks.md wording names it; the restore primitive covers it).
     - on `RESTORED` only: reset the work-tip ref with `lanes.lane_tip.record_tip(repo_root, branch)` (it reads the branch head, now `before`; `lane_tip.py:63-86`), delete the record with `lanes.auto_rebase_record.delete(repo_root, branch, after)` (WP02), and drop the entry: `state.lane_rebase_moves.pop(branch, None)`.
  3. A failed work-tip reset or record delete after a successful restore does NOT turn the outcome into `NOT_RESTORED` (the branch IS restored). Put the residue in the outcome's `reason` (for example `"restored; auto-rebase record <sha12> not deleted"`) so the report shows it, and leave the entry's removal as above. A left record is harmless: FR-004 only reads records of merges still on the lane.
  4. Residue context: `_restore_one` receives the run's `_RunResidue` (`:910-945`); `restore_branch_ref` re-targets it per checkout (the lane checkout is judged with the lane role). Pass it through unchanged.
  5. Update the module docstring: guarantee 2a becomes "Lane branches are report-only EXCEPT the run's own recorded auto-rebase move (`lane_rebase_moves`), which is restored under compare-and-swap from `after` to `before`; any other lane move is never restored." Update the `rebaseline_after_full_restore` docstring sentence "Lanes are report-only and never restored" (`:1080-1082`) to match.
- **Shape** (a sketch, not a prescription):
  ```python
  def _rollback_lane(repo_root, state, branch, snapshot, restore_to, live, context) -> BranchOutcome:
      move = state.lane_rebase_moves.get(branch)
      if not _is_own_move(move, restore_to):
          return BranchOutcome(branch, BranchOutcomeKind.UNCHANGED_BY_RUN, snapshot, live, reason=_LANE_REPORT_ONLY_REASON)
      before, after = move
      if live != after:
          return BranchOutcome(branch, BranchOutcomeKind.LANE_MOVED_SINCE_AUTO_REBASE, snapshot, live, after,
                               reason=..., restored_to_sha=before)
      outcome = _restore_one(repo_root, branch, snapshot, before, live, after, adopted=False, context=context)
      if outcome.kind is BranchOutcomeKind.RESTORED:
          outcome = _after_lane_restore(repo_root, state, branch, after, outcome)
      return outcome
  ```
- **Imports**: `rollback.py` already imports `specify_cli.lanes.compute` (`:100`); importing `specify_cli.lanes.lane_tip` and `specify_cli.lanes.auto_rebase_record` is the same direction (consolidation -> lanes). `lane_tip` must never import `consolidation.*` (`lane_tip.py:13-16`), so there is no cycle.
- **Complexity**: `_rollback_branch` drops a branch; `_rollback_lane` holds the new decisions. Keep both <= 15; extract `_after_lane_restore(...)` for the three follow-ups if needed.
- **Validation**: T018 tests 1 and 3 and T019 step 5 green; `tests/consolidation/test_single_rollback_authority.py` green (no new restore site outside `rollback.py`).
- **Files**: `src/specify_cli/consolidation/rollback.py`.
- **Parallel?**: no.

### Subtask T021 - The new outcome `LANE_MOVED_SINCE_AUTO_REBASE`

- **Purpose**: a lane that moved after this run's auto-rebase merge (an operator commit) is never reset, and the operator is told exactly what is there.
- **Steps**:
  1. Add `LANE_MOVED_SINCE_AUTO_REBASE = "lane_moved_since_auto_rebase"` to `BranchOutcomeKind` (`rollback.py:177-188`).
  2. **Decision (record it in history as a design decision)**: put the new kind in `_OK_KINDS` (`:213-221`) and in the `rebaselineable` exclusion (`:251-272`, next to `KEPT_BY_OPERATOR` and `LANE_MISSING`). Rationale:
     - not re-baselineable: the record (the lane's `lane_rebase_moves` entry, the snapshot) is the only place that says the lane carries this run's merge under the operator's commit, so the executor's re-baseline (`executor.py:836-839`) must not run;
     - "OK" for `fully_restored`: `--abort` keeps the record whenever `fully_restored` is False (`cli/commands/consolidate.py:606-624`), and there is no release mechanism for a lane (`release_branch` binds run-movable branches only, `rollback.py:795-799`). A non-OK kind would wedge `--abort` forever. This mirrors `KEPT_BY_OPERATOR`: kept, reported, abort may finish. After an abort the durable auto-rebase ref (WP02) still names the merge, so FR-004 still recognises it as a tool merge, and the operator commit is judged as today (`LANE_MOVED_AFTER_APPROVAL`), which is US6 AS4.
     This is a design decision the operator may overrule (record it as such in history and in the PR): the moved lane counts as settled for `fully_restored`, and its record is kept. If the operator rules otherwise, change only these two sets and the truth-table row.
  3. `_settle_outcomes` (`:1010-1026`) only touches run-movable branches; lanes are not run-movable (`run_movable_branches`, `:498-501`), so no change there. Confirm with a test.
  4. Rendering:
     - `_render_outcome_line` (`:364-384`): `  kept       <lane>  (moved since this run's auto-rebase merge <after7>, now at <live7>; not restored)`.
     - `_next_step` (`:336-356`): for the new kind, one line for both follow-ups: `<lane>: it holds this run's auto-rebase merge <after7> under later commits (git log --oneline <before7>..<live7>); nothing was reset. The next consolidate judges those commits as it does today.` No `git reset` and no `--force` in the text. Make `_next_step` return a step for this kind even though it is not `NOT_RESTORED` (today it returns `None` for every other kind, `:338-339`; restructure with a small dispatch so the function stays <= 15).
  5. `cli/commands/consolidate._abort_kept_record_message` (`consolidate.py:648-663`) is not owned and needs no change: with the kind in `_OK_KINDS` the abort proceeds.
- **Tests** (in `test_rollback_own_lane_moves.py`, real git):
  1. `test_a_lane_moved_after_the_auto_rebase_is_reported_not_reset`: record `[before, after]`, add a commit on the lane on top of `after`; rollback leaves the lane at the new commit, the outcome kind is the new one, the render names the lane, `before`, `after` and the live tip (US6 AS2).
  2. `test_the_moved_lane_keeps_its_record_and_blocks_the_rebaseline`: `report.rebaselineable is False`, `report.fully_restored is True`, `state.lane_rebase_moves[lane]` still present, the auto-rebase ref still present.
  3. `test_abort_after_a_moved_lane_completes`: through the real CLI (`tests/terminus/rollback_harness.py` style, `run_terminus(mission, ["consolidate", "--mission", slug, "--abort"])`) the abort exits 0 and prints the lane line.
  4. `test_a_dirty_lane_checkout_is_not_restored`: an uncommitted, non-residue edit in the lane worktree makes the restore refuse; the outcome is `NOT_RESTORED` with cause `DIRTY_CHECKOUT` and `blocked_checkout` naming the lane worktree; the lane tip is still `after`; `fully_restored` is False so the record is kept (the existing dirty-checkout next step, `_next_step`, `:347-351`, tells the operator what to do).
  5. `test_a_render_never_suggests_a_destructive_command`: the moved-lane line and its next step contain neither `reset` nor `--force`.
- **Why the new kind and not `NOT_RESTORED`**: `NOT_RESTORED` means "the authority wanted to restore and could not" and keeps `--abort` failing until the operator fixes something. For a moved lane the authority must NOT restore (the operator's commit sits on top), so there is nothing to fix; reporting it as a failure would send the operator looking for a problem that does not exist (the #7382 lesson in `lane_cleanup._refusal_detail`, `lane_cleanup.py:446-459`).
- **Validation**: the five tests; the truth-table row from T019 step 6.
- **Files**: `src/specify_cli/consolidation/rollback.py`, `tests/consolidation/test_rollback_own_lane_moves.py`.
- **Parallel?**: no; T020 and T021 land together.

### Subtask T022 - State lifetime of `lane_rebase_moves`

- **Purpose**: an entry for a lane that was NOT restored must survive whatever the rollback door does next; an entry for a restored lane must not linger.
- **Steps**:
  1. `rebaseline_after_full_restore` (`rollback.py:1044-1125`) clears `lane_rebase_moves` wholesale at `:1099`. Change it to keep the entries of lanes whose outcome in `outcomes` is `LANE_MOVED_SINCE_AUTO_REBASE` or `NOT_RESTORED`, and drop the rest. With T021's decision the executor never calls it in that case (`rebaselineable` is False), so this is defence in depth for any future caller; say so in the docstring.
  2. `_clear_bookkeeping` (`:1029-1041`, run on every full restore) leaves `lane_rebase_moves` alone today; keep it that way (T020 pops restored lanes' entries itself).
  3. `state.py:350-356`: update the field comment. New text: written by `phase_advance` on every auto-rebase merge of the run (WP07); read by lane cleanup (`cleanup_expected_tips`) and by the rollback, which restores `after -> before` under CAS and drops the entry; an entry for a lane reported `LANE_MOVED_SINCE_AUTO_REBASE` is kept. The loader (`_intent_chains_or_empty`, `state.py:396-397`) is unchanged: malformed still loads as `{}` (fail closed: no restore without a well-formed record).
- **Tests**:
  1. `test_rebaseline_keeps_the_moves_of_unrestored_lanes`: call `rebaseline_after_full_restore` directly with one `RESTORED` lane outcome and one `LANE_MOVED_SINCE_AUTO_REBASE` lane outcome; only the second entry remains.
  2. Keep `tests/consolidation/test_lane_cleanup_auto_rebase_6736.py::test_a_full_restore_rebaseline_drops_recorded_moves` (`:424`) green unchanged (no lane outcome in its call: everything is dropped, as before).
  3. `test_lane_rebase_moves_round_trip` (`test_lane_cleanup_auto_rebase_6736.py:241`) unchanged and green.
- **Edge cases**:
  - a resumed attempt after a `LANE_MOVED_SINCE_AUTO_REBASE`: `begin_attempt` sets the lane's restore target to its live tip (moved between attempts, `_lane_attempt_start`, `:699-703`); the kept entry's `before` then differs from the restore target, so T020's rule treats it as report-only on the next rollback. That is correct: the lane is no longer at this run's merge. Pin it with one test.
  - `cleanup_expected_tips` (`lane_cleanup.py:239-249`, not owned) follows a move only from the snapshot tip; after a restore the entry is gone and the lane is at the snapshot again, so cleanup expects the snapshot. No change needed there.
- **Sketch for step 1**:
  ```python
  kept_lanes = {o.branch for o in outcomes if o.kind in (BranchOutcomeKind.LANE_MOVED_SINCE_AUTO_REBASE, BranchOutcomeKind.NOT_RESTORED)}
  kept_moves = {b: m for b, m in state.lane_rebase_moves.items() if b in kept_lanes}
  # ... the existing field loop, with lane_rebase_moves removed from it ...
  if state.lane_rebase_moves != kept_moves:
      state.lane_rebase_moves = kept_moves
      changed = True
  ```
  `outcomes` is an `Iterable`: materialise it once (`tuple(outcomes)`) before `_clear_bookkeeping` consumes it, or the second pass sees nothing.
- **Complexity**: `rebaseline_after_full_restore` is already long; move the lane-moves rule into `_kept_lane_moves(state, outcomes)`.
- **Validation**: the tests above; `tests/consolidation/test_teardown_refusal_resume.py` and `tests/terminus/test_rollback_record_rebaseline.py` green.
- **Files**: `src/specify_cli/consolidation/rollback.py`, `src/specify_cli/consolidation/state.py`, `tests/consolidation/test_rollback_own_lane_moves.py`.
- **Parallel?**: no.

## Test Strategy

Red first (T018, then T019 step 5). Commands (targeted files only):

```bash
uv run --frozen pytest -q tests/consolidation/test_rollback_own_lane_moves.py tests/consolidation/test_rollback_authority.py
uv run --frozen pytest -q tests/consolidation/test_single_rollback_authority.py tests/consolidation/test_lane_cleanup_auto_rebase_6736.py \
  tests/consolidation/test_teardown_refusal_resume.py tests/consolidation/test_executor_rollback_wiring.py \
  tests/consolidation/test_late_window_base_resume.py tests/consolidation/test_state_snapshot_fields.py tests/consolidation/test_abort_remedies.py
uv run --frozen pytest -q tests/terminus/test_rollback_record_rebaseline.py tests/terminus/test_abort_restores_snapshot.py
uv run --frozen pytest -q tests/architectural/test_merge_pipeline_ratchets.py tests/architectural/test_layer_rules.py
make test-fast
```

No full heavy suites and no bare `tests/architectural/`.

Quality gates:

```bash
uv run --frozen ruff check src/specify_cli/consolidation/rollback.py src/specify_cli/consolidation/state.py tests/consolidation/test_rollback_authority.py tests/consolidation/test_rollback_own_lane_moves.py
uv run --frozen ruff format --check --force-exclude src/specify_cli/consolidation/rollback.py src/specify_cli/consolidation/state.py tests/consolidation/test_rollback_authority.py tests/consolidation/test_rollback_own_lane_moves.py
uv run --frozen mypy src/specify_cli/consolidation/rollback.py src/specify_cli/consolidation/state.py
```

Complexity <= 15; no `# noqa`, no `# type: ignore`. Record commands and counts in WP history.

**Tracer notes**: record with `spec-kitty agent tasks add-history WP03 --note "trace(<tooling-friction|approach|design-decisions>): ..."`. Expected entries: the T018 observed outcome at HEAD (with the exact code), the `_OK_KINDS` / `rebaselineable` decision for the new kind, why `resync_checkouts_to_tip` is not called separately, and the narrow-source rule.

## Risks & Mitigations

- **Reversing ADR A2 too widely.** Mitigation: the only restore source is `lane_rebase_moves`; `post_mutation_refs` is ignored for lanes (re-pinned test); a move recorded from another tip is report-only (T019 step 4).
- **Resetting operator work.** Mitigation: CAS on `after`; a dirty lane checkout refuses the resync before the ref moves (`restore_branch_ref` dirty-checks first, `git/ref_advance.py:853-859`); a moved lane is reported, never reset.
- **Wedging `--abort`.** Mitigation: the T021 decision keeps the new kind OK for `fully_restored`; T021 test 3 drives `--abort` through the real CLI.
- **Faking SC-004 by loosening the resume check.** Mitigation: `state.py` changes are limited to the field comment; `lane_tip_cas_ok` is untouched; the review checks it.
- **A fixture that never auto-rebases.** Mitigation: the local builder allocates lane worktrees with `allocate_lane_worktree`, and T018 step 3 asserts the recorded move before any post-fix assertion.

## Report line (contract)

- A test asserts the `LANE_MOVED_SINCE_AUTO_REBASE` report line names the lane, the recorded before and after, and the live tip, and prints no raw git recipe (`contracts/refusal-codes.md`).

## Review Guidance

Anti-fake checks (from `squad2/reviewer-renata.md`, FR-009 findings, and `squad2/doctrine-daphne.md` findings 1 and 9):

- The restore source is `lane_rebase_moves` (tool record), never `post_mutation_refs`: the re-pinned test still sets a lane in `post_mutation_refs` and expects `UNCHANGED_BY_RUN`.
- No change to `state.lane_tip_cas_ok` or to the resume guards in `phase_claim.py`; SC-004 is met by restoring the lane, not by tolerating the merge.
- The lane checkout is resynced (T018 test 3 checks HEAD, index and working tree), and the lane work-tip ref is reset (T018 test 1).
- The moved-lane outcome is distinct, not re-baselineable, and keeps its record; a foreign commit after the rollback is never reset.
- `test_single_rollback_authority.py` is green and the diff adds no `restore_branch_ref` call outside `rollback.py`.
- The red-first evidence for T018 is in WP history with the actual code observed at HEAD.
- T018 test 2 runs on the CLEAN shape, asserts exit 0 on the second run and that no commit of the first run's recorded move is named; there is no "does not name `<merge>`" fallback. T018 test 4 (failed after the auto-rebase) is present.
- The fixture allocates lane worktrees (`allocate_lane_worktree`); `build_coord_mission_shared_file` is not used.
- Confirm mypy ran and passed in addition to pytest.

## Progress & Status

Progress, history, and status all live in the status event log (`status.events.jsonl`), never in this prompt file. Do **not** hand-edit a history section here.

- **Record a progress note**: `spec-kitty agent tasks add-history WP03 --note "<what you did>"`
- **Change WP status**: `spec-kitty agent tasks move-task WP03 --to <status>`
- **View history and status**: `spec-kitty agent tasks status`
