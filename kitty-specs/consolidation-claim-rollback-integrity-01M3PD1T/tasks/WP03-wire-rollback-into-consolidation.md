---
work_package_id: WP03
title: 'Wire the authority into consolidation (#5318, #5332) + truthful text'
dependencies:
- WP01
- WP02
requirement_refs:
- C-001
- C-002
- C-003
- C-004
- FR-003
- FR-004
- FR-006
- FR-009
- FR-010
planning_base_branch: issue-5338-consolidation-claim-rollback-integrity
merge_target_branch: issue-5338-consolidation-claim-rollback-integrity
branch_strategy: Planning artifacts for this mission were generated on issue-5338-consolidation-claim-rollback-integrity. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5338-consolidation-claim-rollback-integrity unless the human explicitly redirects the landing branch.
subtasks:
- T012
- T013
- T014
- T015
- T016
- T017
phase: Phase 2 - Integration
history:
- at: '2026-09-29T13:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/terminus/
create_intent:
- tests/terminus/test_repro_5318.py
- tests/terminus/test_repro_5318_lanes.py
- tests/terminus/test_repro_5332.py
- tests/terminus/test_repro_refuse_restores_all.py
- tests/consolidation/test_single_rollback_authority.py
- tests/consolidation/test_executor_rollback_wiring.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/consolidation/test_merge_state_authority.py
- tests/specify_cli/cli/commands/test_merge_cli_golden.py
- src/specify_cli/consolidation/executor.py
- tests/terminus/test_repro_5318.py
- tests/terminus/test_repro_5318_lanes.py
- tests/terminus/test_repro_5332.py
- tests/terminus/test_repro_refuse_restores_all.py
- tests/consolidation/test_single_rollback_authority.py
- tests/consolidation/test_executor_rollback_wiring.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Wire the authority into consolidation (#5318, #5332) + truthful text

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⛔ HARD RULE: no heavy full suites during the mission

During implement and **every WP review**, you AND every implementer/reviewer subagent you dispatch must NEVER run full or heavy suites:
- no whole `tests/architectural/`, no e2e or full-integration suites, no performance/stress/timing suites;
- no `make test-full`, no whole-repo pytest.

Per WP, run only:
- the test files covering the files the WP touches;
- the owning module's fast tier;
- the specific NAMED architectural gate files the change implicates.

Leave broad sweeps to the END of the mission or to CI (`NO_FULL_HEAVY_SUITES_IN_MISSION`).

---

## ⚠️ IMPORTANT: Review Feedback

Check `spec-kitty agent tasks status --mission consolidation-claim-rollback-integrity-01M3PD1T` and the Activity Log for a `review_ref`; if present, every feedback item is your TODO list.

---

## Ownership note (recorded leeway — Standing Order #8)

`src/specify_cli/consolidation/executor.py` is owned by both WP01 and this WP (finalize accepts it because this WP **depends on WP01** — strictly sequential, no parallel collision). Keep executor edits to exactly the sites listed below and record them in the Activity Log.

## Objectives & Success Criteria

With WP02's authority available, make every **reconciliation-gate FAIL/REFUSE and squash-projection refusal** restore every snapshotted branch and print the truthful rollback report (#5318, #5332, FR-004/006/009). Snapshot captured once before the first mutation (FR-003); post-mutation tips recorded after each mutating phase (FR-007 expected values).

Done means (all through real `spec-kitty consolidate` runs, asserting real SHAs):
- #5318 coord: after a gate FAIL, target AND coordination/mission branch are at their pre-run SHAs; `state.json` no longer claims `mission_number_baked` / `completed_wps`; after removing the cause, a fresh run (with and without `--abort` in between — the `--abort` half lands in WP04, so here test the `--resume` and plain re-run paths) exits 0 with work attributed.
- #5318 LANES: the mission branch (`kitty/mission-…`), today left at the lane-merge + bake commit, is back at its pre-run SHA.
- #5332 coord: a projection refusal restores and exits non-zero; on the resume short-circuit with a PASS anchor for the current target tip, the verified landing is KEPT (FR-011) and the report says so.
- Fresh "all lanes folded into the coordination branch" run: the gate REFUSE (empty authored-blob set) now restores target + coordination branch and the output never says "no refs/worktrees were mutated".
- AST pin proves the wiring is not vacuous.

## Context & Constraints

- Read: `spec.md`, `plan.md` IC-03/IC-05, `research.md` D2–D5 + D8, `contracts/rollback-authority.md`, and WP02's `consolidation/rollback.py` API.
- Reference repros: `kitty-specs/consolidation-claim-rollback-integrity-01M3PD1T/research/coord_repro_reference.py.txt` (`test_5318` shape) and the LANES builder `tests/terminus/lanes_fixture.py` (WP02).
- Live-verified facts (post-plan residual hunt):
  - In LANES, `_capture_coord_checkpoint` resolves to the **target** (checkpoint = (target, pre-mutation target sha)); the #5332 "bookkeeping did not land" refusal is effectively unreachable in LANES → its repro uses coordination topology.
  - Both `_assert_squash_projected_content_landed` refusals are `typer.Exit(1)` raised INSIDE `_phase_reconcile_before_teardown` (normal PASS path :~2429 and resume short-circuit :~2419-2423), so one driver-level wrapper catches them.
  - Fresh cheap red: `fold_lanes_into_mission_branch(m, all_wps)` (conftest :673) then plain consolidate → target `35f6333→00edd29`, coord `7449419→04431ce`, gate REFUSE "no approved lane resolved any commits … authored-blob set is empty", text falsely says "no refs/worktrees were mutated", no rollback.
- **C-001 (#5359)**: do NOT edit `_phase_reconcile_before_teardown`, `_rollback_target_after_failed_reconciliation`, `recovery_guidance`, `verify`, `build_approved_wp_set`. The ONLY #5359-touched function you edit is `_run_lane_based_consolidation_locked`, and only the single line that calls `_phase_reconcile_before_teardown(run)` (+ the post-tips call just before it). Expect a textual rebase conflict there — note it in the Activity Log.
- Frozen phase order (`tests/consolidation/test_executor_phase_boundary.py::test_locked_driver_calls_phases_in_frozen_order`) checks order textually (`src.index`) and does not list `_phase_reconcile_before_teardown(run)`, so it does not constrain the wrapper. Keep the literal call in the driver inside the `try` anyway — the AST pin (T016) keys on it.

## Branch Strategy

- **Strategy**: lanes (computed by finalize-tasks; see `lanes.json`)
- **Planning base branch**: `issue-5338-consolidation-claim-rollback-integrity`
- **Merge target branch**: `issue-5338-consolidation-claim-rollback-integrity`

Start with `spec-kitty agent action implement WP03 --agent claude --mission consolidation-claim-rollback-integrity-01M3PD1T` (after WP01 and WP02 are approved).

## Subtasks & Detailed Guidance

### Subtask T012 – Red-first real-CLI repros (commit FIRST)

- `tests/terminus/test_repro_5318.py` (coord, `build_coord_mission` + `plant_canceled_commit`): record SHAs (target, coord/mission branch, lanes) → `consolidate --yes` (gate FAIL) → assert target AND coordination branch back at pre-run SHAs, lanes unchanged, `mission_number_baked` false and `completed_wps` empty in state. RED today: coord branch keeps lane merge + bake + done + seed commits (grounding repro: `ade39f2`, `b13a898`, …).
  - Second test: after the FAIL, remove the cause (drop the planted canceled commit from the carrier lane with plain git on the lane branch, or cancel/re-approve per the fixture's options — pick the simplest real removal), then `consolidate --resume --yes` and (separately) a plain `consolidate --yes`; assert exit 0 and the approved WPs' files are on the target.
- `tests/terminus/test_repro_5318_lanes.py` (LANES builder, target `develop`): FAIL → mission branch back at its pre-run SHA (RED today: stays at lane-merge + bake commit `95b8be9` in the hunt).
- `tests/terminus/test_repro_5332.py` (coord): produce a squash-projection refusal on a FRESH run. Real trigger (post-tasks finding 12, try first): a projected path with no merge driver, e.g. `kitty-specs/<slug>/notes/n.md` — it counts as bookkeeping for the blob-attribution axis (gate PASSes), stays projected per the denylist, and has no `.gitattributes` driver so `driver_replay_expected_bytes` raises `GitProbeError` and the proof returns False. Setup: baseline `n.md` in the bootstrap commit, the lane edits line 1, and a non-overlapping line change is committed on the target before consolidating (stock squash merges cleanly while pre-squash ≠ checkpoint → REFUSE). If that fails, fall back to an in-process production-shell test that monkeypatches ONLY `projected_content_matches_target` → False (say so in the docstring; still assert real SHAs). Assert (post-tasks BLOCKER 1): exit 1, target + coordination branch RESTORED lines in the report, target/coord SHAs == pre-run, and `state.reconciliation_passed_target_sha` is null afterwards. Plus the FR-011 control: a RESUME whose persisted anchor (from an EARLIER attempt) equals the target tip and a projection refusal → landing kept, report "Kept the landing…", exit 1.
- `tests/terminus/test_repro_refuse_restores_all.py`: fresh fold-all-lanes REFUSE → target + coordination branch restored; output lacks "no refs/worktrees were mutated"; contains the rollback report lines.
- Markers: `integration`, `git_repo`, `regression` (like `test_repro_5021.py`; `regression` = issue-pinned e2e in pytest.ini, kept after the fix).
- **Vacuous-oracle guard (finding 13)**: in the #5318 test, since today's code already restores the target on FAIL, the load-bearing assertions are the coordination/mission branch + state ones. Also assert `git reflog refs/heads/<coord>` gained ≥ 2 entries during the run and its newest entry equals the pre-run SHA, and that the report contains `restored <coord> <post>→<pre>` with post ≠ pre. Run on the WP base; record the failing assertions. Commit: `test(consolidate): red-first repros for full-snapshot rollback on gate/projection refusal (#5318 #5332)`.

### Subtask T013 – Capture the snapshot once, before the first mutation

- In `executor.py`, right after `_capture_reconciliation_claim(run)` inside the `with _clear_fresh_record_on_pre_mutation_exit(run):` block — **do not edit `_run_lane_based_consolidation_locked` for this**; instead call it at the END of `_capture_reconciliation_claim` (WP01-owned, not #5359-touched), after WP01's refusal check:
  ```python
  rollback.capture_pre_mutation_snapshot(run.main_repo, run.state, run.lanes_manifest,
                                         coord_ref=run.coord_checkpoint.ref if run.coord_checkpoint else None)
  ```
  A resume reuses the persisted map (the function never recaptures). Then call `rollback.begin_attempt(run.main_repo, run.state)` (every attempt, fresh and resume) to compute this attempt's `restore_targets`. Warn (console) about any skipped missing lane branch.
- LANES: `coord_checkpoint.ref` is the target → dedupe happens in WP02's capture; assert in a unit test (`tests/consolidation/test_executor_rollback_wiring.py`) that the snapshot keys for a LANES run are {target, mission branch, lane branches} with no duplicate.

### Subtask T014 – Record post-mutation tips after each mutating phase

- Call `rollback.record_post_mutation_tips(run.main_repo, run.state)` at the END of each of: `_phase_merge_lanes`, `_phase_bake_and_pre_target_done`, `_phase_mission_to_target`, `_phase_record_done_and_project`, `_phase_commit_and_assert` (none are #5359-touched) — **before every early `return`** (bake :~755 and mission→target :~1440 planning-only returns) or via `try/finally` — and once immediately before the gate call in the driver (T015). Branch movers confirmed (post-tasks Q5): merge_lanes → coord/mission branch; bake → mission/coord branch and the primary-tree bake fallback commits on the TARGET (:~780); mission_to_target → target; record_done_and_project → coord via `_commit_coord_seed_events`; commit_and_assert → target. `_phase_capture_and_baseline` moves no ref.
- **In-phase rollbacks (finding 4)**: also call `record_post_mutation_tips` at the end of `_rollback_to_pre_mutation_checkpoint`, `_restore_and_guard_coord_coherence` and `_restore_pre_target_if_at_baseline` (they create revert commits; without a record `--abort` would be sticky). Keep each function ≤ 15 complexity.
- Unit test: after each phase in a real fixture run the persisted `post_mutation_refs` equals the live tips.

### Subtask T015 – The driver wrapper (the one #5359-touched line)

- Replace the single `_phase_reconcile_before_teardown(run)` call in `_run_lane_based_consolidation_locked` with:
  ```python
  rollback.record_post_mutation_tips(run.main_repo, run.state)
  anchor_before = run.state.reconciliation_passed_target_sha
  try:
      _phase_reconcile_before_teardown(run)
  except typer.Exit as exc:
      if exc.exit_code:
          _report_rollback(run, anchor_before=anchor_before)   # module-level helper below
      raise
  ```
  **Post-tasks BLOCKER 1**: on the fresh PASS path `_phase_reconcile_before_teardown` persists THIS run's PASS anchor (`_record_reconciliation_pass`) and only then runs the projection proof; if the projection refuses, FR-011 would see this run's own anchor and refuse to roll back. `_report_rollback` therefore restores `run.state.reconciliation_passed_target_sha = anchor_before` (+ `save_state`) when it changed during this call, BEFORE calling the authority. An anchor from an EARLIER attempt (resume short-circuit) is left intact, so FR-011 keeps that verified landing.
  and add `def _report_rollback(run) -> None: report = rollback.rollback_to_snapshot(run.main_repo, run.state, target_branch=run.lanes_manifest.target_branch); console.print(report.render())` plus, when the primary checkout's branch is the target and it was RESTORED, nothing more (resync is done inside the authority).
- Make `_resume_reconciliation_already_passed` delegate to `state.reconciliation_passed_for_tip(run.state, current_sha)` (single predicate).
- Idempotence with today's target-only restore inside the gate (FAIL path): the wrapper sees the target ALREADY_AT_SNAPSHOT — assert that in the #5318 test's report.
- Do not catch other exception types here (post-PASS exits and in-phase exits are out of scope — residual #5385).

### Subtask T016 – AST pin `tests/consolidation/test_single_rollback_authority.py`

- Non-vacuous architectural pin (DIRECTIVE_043 / Standing Order #5):
  1. `rollback_to_snapshot` is called from exactly the allowed callers: `executor._report_rollback` and (after WP04) the `cli/commands/consolidate` abort helper — assert the discovered caller set ⊆ allowlist and ≥ `_CALLER_FLOOR` (named constant = 1 here, with a comment: WP04 raises it to 2; tasks.md T016's "≥ 2" is the end state after WP04).
  2. `restore_branch_ref(..., resync_checkouts=True)` is called only from `consolidation/rollback.py`.
  3. The driver's `_phase_reconcile_before_teardown` call sits inside a `try` whose handler calls `_report_rollback`.
  4. Self-mutation test: run the same scanner over a synthetic source string that calls `_phase_reconcile_before_teardown(run)` without the wrapper / calls `restore_branch_ref(resync_checkouts=True)` from elsewhere → the scanner reports the violation.

### Subtask T017 – Re-pin stale tests; truthful text audit; named gates

- `grep -rn "FOLD-5\|Nothing was torn down\|no refs/worktrees were mutated\|REFUSE.*keeps\|_rollback_target_after_failed_reconciliation" tests/` — tests encoding "projection refusal never rolls back" or "a REFUSE leaves the target advanced" encode a superseded product direction (research D4, operator decision) → re-pin to the new contract with a dated rationale; `tests/specify_cli/cli/commands/test_merge_cli_golden.py` golden output → re-pin if the appended report changes it.
- Audit executor-owned refusal text (:~2553/:~2576 projection messages): they stay truthful ("Nothing was torn down") because the rollback report is appended; do not claim anything about refs there.
- `coordination/teardown.py:~115` ("no refs/worktrees were mutated") is raised AFTER a PASS (target already advanced, post-PASS exit — out of scope): leave the code; add one line to the Activity Log noting it for the #5385 follow-up.
- Run (record counts):
  - `PWHEADLESS=1 .venv/bin/python -m pytest tests/terminus/test_repro_5318.py tests/terminus/test_repro_5318_lanes.py tests/terminus/test_repro_5332.py tests/terminus/test_repro_refuse_restores_all.py tests/terminus/test_repro_5338.py tests/terminus/test_repro_4945.py tests/terminus/test_repro_5021.py tests/terminus/test_repro_5038.py -q`
  - `tests/consolidation/test_single_rollback_authority.py tests/consolidation/test_executor_rollback_wiring.py tests/consolidation/test_executor_phase_boundary.py tests/consolidation/test_reconciliation.py tests/consolidation/test_merge_state_authority.py`
  - fast tier `tests/consolidation -m "fast or unit"`; `tests/specify_cli/cli/commands/test_merge_cli_golden.py`
  - NAMED gates: `tests/architectural/test_merge_pipeline_ratchets.py`, `tests/architectural/test_destructive_op_routing.py`, `tests/architectural/test_layer_rules.py`, `tests/architectural/test_no_dead_symbols.py`, `tests/architectural/test_no_legacy_terminology.py`
  - ruff check/format on touched files; mypy on `executor.py`, `rollback.py` (no new errors vs base count).

## Risks & Mitigations

- **Restoring the coordination branch drops pre-target `done` events on it** — intended (they belonged to the refused attempt); assert the next run re-records them.
- **Dirty coordination worktree** → NOT_RESTORED and reported (never forced).
- **#5359 conflict** on the driver lines → minimal edit; after #5359 lands, its REFUSE target-restore becomes a redundant backstop (ALREADY_AT_SNAPSHOT).
- **Frozen phase-order test** → keep the literal call.

## Review Guidance

- Reviewer ≠ implementer; verify red→green per repro at WP base vs tip.
- Verify every acceptance assert reads real `git rev-parse` SHAs and state bytes (#5344-class vacuous-oracle guard: assert the pre-run SHA differs from the post-FAIL-pre-fix SHA in the red run, so the restore assertion is meaningful).
- Verify only the allowed #5359-touched line changed (`git diff` of `_run_lane_based_consolidation_locked`).
- HARD RULE respected.

## Activity Log

- 2026-09-29T13:00:00Z – system – Prompt created.
