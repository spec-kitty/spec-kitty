---
work_package_id: WP18
title: Consolidation executor and materialize writers move to the accessor
dependencies:
- WP17
requirement_refs:
- FR-003
- FR-014
- FR-016
- NFR-002
- C-008
planning_base_branch: issue-5440-coord-artifact-single-home
merge_target_branch: issue-5440-coord-artifact-single-home
branch_strategy: Planning artifacts for this mission were generated on issue-5440-coord-artifact-single-home. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5440-coord-artifact-single-home unless the human explicitly redirects the landing branch.
subtasks:
- T097
- T098
- T099
- T100
- T101
- T102
phase: Phase 6 - Decision doctor and consolidation
history:
- at: '2026-10-01T08:36:27Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
agent: claude
authoritative_surface: src/specify_cli/consolidation/executor.py
create_intent: []
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/consolidation/executor.py
- src/specify_cli/cli/commands/materialize.py
- tests/consolidation/test_executor_coord_reconcile.py
- tests/consolidation/test_done_bookkeeping_seam.py
- tests/cli/commands/test_merge_status_commit.py
- tests/specify_cli/cli/commands/test_materialize.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
assignee: ''
shell_pid: ''
---

# Work Package Prompt: WP18 – Consolidation executor and materialize writers move to the accessor

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (or any user-defined profile), and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## ⚠️ IMPORTANT: Review Feedback

**Read this first if you are implementing this task!**

- **Has review feedback?**: Check the `review_ref` field in the event log (via `spec-kitty agent tasks status` or the Activity Log below).
- **You must address all feedback** before your work is complete. Feedback items are your implementation TODO list.
- **Report progress**: As you address each feedback item, update the Activity Log explaining what you changed.

## Review Feedback

*[If this WP was returned from review, the reviewer feedback reference appears in the Activity Log below or in the status event log.]*

---

## Markdown Formatting

Wrap HTML/XML tags in backticks: `` `<div>` ``, `` `<script>` ``
Use language identifiers in code blocks: ````python`, ````bash`

---

## Objectives & Success Criteria

Operator ruling Q4 requires the consolidation executor's status writes and `materialize`'s derived-view writes to stop deriving their write location from read resolvers. That lets the FR-014 gate (WP20) start with an **empty** allowlist. When this WP is done:

- **`_run_lane_based_consolidation`** (unlocked pre-phase) resolves the Mission's status dir via `placement_seam(...).write_dir(STATUS_STATE)`:
  - a pre-fix EMPTY coordination surface is seeded once, before the merge lock and the pre-mutation snapshots, and the done bookkeeping lands in the coordination log, not the repository root checkout's log (US2.9, R22);
  - an UNMATERIALIZED surface with a local branch is materialized, and consolidation proceeds instead of aborting (deliberate behaviour change, R23 re-pin);
  - a remote-only branch still aborts with "Merge aborted before any state change", and so does a seed fork.
- **`_phase_baseline_and_surface`** stops re-deriving the surface. `run.canonical_events_path` comes from `run.feature_dir` (one authority per run), except the completed-Mission `--resume` case, which keeps today's PRIMARY answer and `done_marked_before_target` (R1d characterization).
- **`spec-kitty materialize`** (with `--mission` or for all Missions) writes the derived views for coordination-routed Missions from the coordination surface's log. `lanes`/`single_branch` are unchanged (C-008), and a remote-only branch is reported per Mission in `errors[]` without aborting the loop (R24).
- **Terminus integrity is preserved**: `--resume` state, rollback authority, reconciliation, dry-run side-effect-freedom. Every guard file in T102 stays green, and strict `xfail`s stay `xfail`.

## Context & Constraints

- **Spec**: FR-003 (consolidation executor's status writes; `materialize`'s `status.json`), FR-014 (no allowlist needed), FR-016 (R22, R23, R24, R1d), NFR-002, C-008; US2.9.
- **Plan**: IC-18. Shared-file map: `consolidation/executor.py` is touched by IC-12 (WP17, the preflight and porcelain message, already landed in this lane) and IC-18 (here).
- **Research**: D21 is the authority for this WP (sites, decisions, risks, guards). Also D2 (lock ordering: the seed takes the status lock in the unlocked pre-phase, before the merge lock) and D4/D20 (state handling inside `write_dir`).
- **Data model**: §7 "Consolidation seed (IC-18)": the seed is part of the pre-mutation state and is never rolled back.
- **Depends on**:
  - WP17 (same lane; executor edits already present);
  - WP04 (`PlacementSeam.write_dir`; via WP12 → WP05 → WP04);
  - WP03 (`COORD_SEED_FORK_REFUSED` / `CoordSeedForkRefused`);
  - WP02 (`make_prefix_coord_mission` builders).
- **Charter**: `.kittify/charter/charter.md`; `spec-kitty charter context --action implement`. ATDD-first (C-011). This is terminus-integrity machinery (#5001), so apply the highest rigour.
- **Model discipline**: implement = sonnet (`claude-sonnet-5`); review = opus.
- **Terminology**: say Mission, never feature. "Consolidate" here is **local lane consolidation** into the local target branch, never a publish to origin. Name the sense of "primary": the repository root checkout, the PRIMARY partition, or the target branch.
- **C-006**: run each named guard file, never the directory.
- **Fixture semantics across lanes (post-tasks squad P-m5):** pre-fix assertions use WP02's `make_prefix_coord_mission`; `make_coord_mission` carries only shape-agnostic invariants (its shape changes when WP06 lands); use `make_coord_mission(..., materialized=True)` when a test needs a deterministic MATERIALIZED coordination surface in every lane.
- **Brownfield scout (binding read)**: before coding, read `## WP18` in `kitty-specs/coord-artifact-single-home-01M3V4BE/research/brownfield-scout-wp12-22.md` (plus its "Cross-cutting" section where present). Its corrections are folded into the "Binding corrections" section below, which overrides conflicting text above.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-5440-coord-artifact-single-home; completed changes must merge back into issue-5440-coord-artifact-single-home.
- **Planning base branch**: issue-5440-coord-artifact-single-home
- **Merge target branch**: issue-5440-coord-artifact-single-home
- `finalize-tasks` allocates execution worktrees per computed lane from `lanes.json`. Start with `spec-kitty agent action implement WP18 --agent claude`, and use the resolved workspace path.
- **Lane sharing**: `consolidation/executor.py` is shared with WP17, which is upstream (dependency-ordered and deliberate), so it runs in **lane B**: WP17 → WP18. WP17's edits (`_pre_mutation_safety_preflight`, the porcelain-invariant message) are at your base; do not rework them.

## Subtasks & Detailed Guidance

### Subtask T097 – R1d characterization pin first (green at base and after)

- **Purpose**: Pin the completed-Mission `--resume` answer that T100 must preserve before touching `_phase_baseline_and_surface`. This is a characterization test, not a reproduction: it is green at base and must stay green.
- **Steps**:
  1. In `tests/consolidation/test_executor_coord_reconcile.py`, add `test_completed_mission_resume_keeps_primary_events_path`.
  2. Build a coordination-routed Mission whose primary Mission is **completed**, meaning `_primary_mission_is_completed` (`coordination/surface_resolver.py:1113`) is true for the repository root checkout's Mission dir. This is the state after a landed consolidation, when `--resume` re-enters. Reuse the file's existing fixtures where possible.
  3. Drive `_phase_baseline_and_surface` (executor.py:799) with a constructed `_MergeRunState` (follow existing tests in this file or `tests/consolidation/test_done_bookkeeping_seam.py` for how they build `run`). Assert:
     - `run.canonical_events_path` is the PRIMARY (repository root checkout) path today's `resolve_status_surface` returns;
     - `run.canonical_status_path` is its sibling `status.json`;
     - `run.done_marked_before_target` has today's value.
  4. Commit it alone: `test(consolidation): characterize completed-Mission resume events path (R1d, WP18)`.
- **Files**: `tests/consolidation/test_executor_coord_reconcile.py`.
- **Validation**: green on your base. Record that in the activity log.
- **Edge cases**:
  - `planning_artifact_only` Missions: if the existing tests show a different branch for them, pin that too.
  - Do not mock `resolve_status_surface`. The test must observe the real answer, or it cannot catch a change.

### Subtask T098 – Red-first R22, R23 split, R24 (ATDD commit)

- **Purpose**: Reproduce the defective (or deliberately changing) behaviour through the pre-existing entry points.
- **Steps**:
  1. **R22** `tests/consolidation/test_done_bookkeeping_seam.py::test_pre_fix_empty_coord_mission_records_done_on_coordination_surface`:
     - entry point `_run_lane_based_consolidation`, the same entry as `tests/cli/commands/test_merge_status_commit.py:289`;
     - fixture (WP02 `make_prefix_coord_mission(worktree="empty")`, plus whatever lanes/approved-WP setup the existing seam tests use): a local coordination branch, an EMPTY coordination worktree, and the creation status events in the repository root checkout's log.
     - After the run, assert:
       - the `done` events are in the **coordination** log;
       - the coordination branch carries exactly one seed commit (`chore(<mission>): seed coordination surface`) before the merge's commits;
       - the repository root checkout's log is restored to its committed state.
     - Red at base: `run.feature_dir` is the root dir (`read_dir` EMPTY → PRIMARY), so `done` lands in the root log.
  2. **R23**: split `tests/cli/commands/test_merge_status_commit.py::TestUnmaterializedCoordWorktreeMerge::test_lane_based_merge_exits_cleanly_on_unmaterialized_coord_worktree` (L271) into two tests.
     - `test_local_branch_unmaterialized_coord_is_materialized_before_merge`: the local branch exists and the worktree was removed. Assert no "Merge aborted" and that after the surface phase the surface is MATERIALIZED (the worktree exists and holds the Mission dir). Red at base: exit 1 with "Merge aborted before any state change … Materialize the coordination worktree".
     - `test_remote_only_coord_branch_still_aborts_before_state_change`: the branch is only on a bare remote (#4970). Keep the original assertions: exit 1, the same message, no ref moved. This is a green control.
     - The split is a **deliberate behaviour change under ruling Q4**, not a stale test. Say so in the test docstring and the activity log.
  3. **R24** `tests/specify_cli/cli/commands/test_materialize.py::test_materialize_all_writes_status_json_on_coordination_surface`:
     - CLI `spec-kitty materialize` (no `--mission`; `--json`) on a MATERIALIZED coordination-routed Mission whose repository root checkout copy of `status.events.jsonl` is stale (fewer events);
     - assert the derived views reflect the **coordination** log (for example the WP lane counts in `status.json`/`board-summary.json` under `.kittify/derived/<mission>/`, and/or `status.json` in the coordination Mission dir — check which files `write_derived_views`/`materialize()` write today and assert the one the reducer writes into the Mission dir).
     - Red at base: the loop iterates the repository root checkout's `kitty-specs/` dirs and reduces the stale log.
  4. Control `::test_materialize_lanes_mission_unchanged`: a `lanes` Mission gives the same output and paths as before. Green.
  5. Commit the red tests alone, and record the red evidence.
- **Files**: `tests/consolidation/test_done_bookkeeping_seam.py`, `tests/cli/commands/test_merge_status_commit.py`, `tests/specify_cli/cli/commands/test_materialize.py`.
- **Edge cases**:
  - R22's fixture must take the **real** consolidation path, not a stub harness; `test_merge_status_commit.py:242` describes replacing a 17-patch harness, so follow its non-stub pattern.
  - Keep the R23 remote-only variant's assertions byte-for-byte from the original test.

### Subtask T099 – `_run_lane_based_consolidation` resolves the status dir via `write_dir`

- **Purpose**: Research D21 point 1. This is the executor's COORD write location for the done bookkeeping, the birth cutover and reads.
- **Steps**:
  1. At `executor.py` ≈L4181 (`feature_dir = seam.read_dir(MissionArtifactKind.STATUS_STATE)` inside `_run_lane_based_consolidation`, def at L4114), switch to `feature_dir = seam.write_dir(MissionArtifactKind.STATUS_STATE).path`. Keep the local name.
     - `run.feature_dir` (≈L4332) feeds `_record_merged_wps_done_for_merge` (≈L892 → `done_bookkeeping.py:722`), the birth cutover (`status_feature_dir`, ≈L1744/L1821/L4229) and reads (≈L592, L3090).
  2. Keep both existing `except` arms with their exact rendering:
     - `CoordinationBranchDeleted` → "Recover the mission's status authority";
     - `CoordinationWorktreeUnmaterialized` → now raised only for the remote-only branch → "Materialize the coordination worktree".
     - Update that hint to name the recovery for a remote-only branch (create the local tracking branch, for example `git branch <coord> origin/<coord>`, then re-run), because the local-branch case no longer reaches it.
  3. Add a third arm for `CoordSeedForkRefused` (code `COORD_SEED_FORK_REFUSED`) with the same "Merge aborted before any state change" rendering and a hint to run `spec-kitty doctor decisions`. Also catch `FeatureStatusLockTimeoutError` (`STATUS_LOCK_HELD`) if `write_dir` can raise it here, with the same clean abort.
  4. Ordering invariant: this call precedes the global merge lock and both pre-mutation captures:
     - `_capture_pre_mutation_coord_checkpoint` (L1064, called at L3748);
     - `rollback.capture_pre_mutation_snapshot` (L2519).
     A seed commit is therefore part of the pre-mutation state, and a later FAIL/REFUSE rollback never undoes it. Add a comment stating this, and assert it in R22: `pre_mutation_coord_sha` equals the seed commit.
  5. Lock ordering (D2/D21): the seed takes the status lock here, outside the merge lock, so there is no inversion. The locked driver's status writes re-enter the reentrant status lock as today.
- **Files**: `src/specify_cli/consolidation/executor.py`.
- **Validation**:
  - R22 and R23 (local) are green; the R23 remote-only control is green.
  - `tests/consolidation/test_coord_deleted_degrade_paths.py` is green.
- **Edge cases**:
  - Pre-fix *forked* Mission: the seed refuses and consolidation aborts cleanly with nothing moved.
  - Owned checkout: `placement_seam(..., owned=...)` must be built as the function builds it today.
  - `--dry-run` does not reach this point; see T100.
- **`WriteLocation.checkout_root` (post-tasks squad P-M3):** take the checkout root from `write_dir(kind).checkout_root` (WP03/WP04). Never derive it as `.path.parent.parent` or by guessing a worktree name.

### Subtask T100 – `_phase_baseline_and_surface` uses the run's single authority

- **Purpose**: Research D21 point 2. One status-surface authority per run, preserving the completed-Mission `--resume` exception.
- **Steps**:
  1. In `_phase_baseline_and_surface` (L799; locked, called at L3775), ≈L825 currently does `status_surface_path = resolve_status_surface(run.main_repo, run.mission_slug)`. Replace it with:
     - if the primary Mission is completed (the `--resume`-after-landing case; reuse `_primary_mission_is_completed` or the same predicate `resolve_status_surface` uses at surface_resolver.py ≈L1267, without importing a private name across modules if a public one exists): keep today's answer (call `resolve_status_surface` as now). This is the consolidation projection's sanctioned exception (FR-008); the read is of records already projected to the target.
     - else: `status_surface_path = run.feature_dir / "status.events.jsonl"`.
  2. Keep the `done_marked_before_target` computation unchanged in form (`is_under_worktrees_segment(status_surface_path) and not run.planning_artifact_only` or `lands_mission_branch(...)`). For a pre-fix EMPTY Mission that was seeded in T099, the flag flips to the coordination value, which is the post-fix behaviour every coordination Mission already has (research D21).
  3. `consolidate --dry-run` / `consolidation/forecast.py` must stay side-effect-free: do not add any `write_dir` call on the forecast path (`tests/consolidation/test_dry_run_fails_closed_on_unmaterialized_coord.py`).
  4. Keep C901 of `_phase_baseline_and_surface` ≤ 15. Extract `_resolve_run_status_surface(run) -> Path` with focused tests if needed.
- **Files**: `executor.py`.
- **Validation**: R1d is still green; R22 is green (the `done` events path agrees with `run.feature_dir`); the done-bookkeeping and rollback-coherence guards are green.
- **Edge cases**:
  - `--resume` of an interrupted run on a MATERIALIZED surface: `write_dir` is side-effect-free, so the resume is unaffected.
  - The persisted `pre_mutation_refs`, `pre_mutation_coord_sha`, `pre_interrupt_lane_tips` and `reconciliation_passed_for_tip` must be untouched (CLAUDE.md "never recaptured on resume").

### Subtask T101 – `materialize` resolves coordination Missions via `write_dir`

- **Purpose**: Research D21 point 3; FR-003 writer family "`materialize`'s `status.json`".
- **Steps**:
  1. `_resolve_selected_dir` (`materialize.py:26`; today `placement_seam(...).read_dir(STATUS_STATE)` at ≈L31) is the `--mission` path. For coordination-routed Missions, return `write_dir(STATUS_STATE).path`.
     - Determine the topology from the Mission's `meta.json` on the PRIMARY partition (use the existing topology resolver; do not parse JSON by hand if a helper exists).
     - Non-coordination topologies keep `read_dir` (C-008); for them it is identical.
  2. All-Missions loop (≈L103-110; today `feature_dirs = sorted(p for p in specs_dir.iterdir() ...)` over repository-root dirs). Per Mission dir:
     - read its `meta.json` topology first;
     - coordination-routed → replace the dir with `write_dir(STATUS_STATE).path`;
     - else keep it.
     - Wrap per-Mission resolution so a remote-only branch (`CoordinationWorktreeUnmaterialized`), DELETED or seed fork becomes an `errors[]` entry for that Mission (`"<slug>: <code>: <message>"`) and the loop continues. This reuses the existing per-Mission `except` at ≈L129 pattern; do not abort.
  3. Help text and docstring: state that the command may materialize, and for pre-fix Missions seed, coordination surfaces (one `git worktree add` per coordination-routed Mission, done once).
  4. Keep `materialize` and helpers ≤ 15 C901: extract `_mission_dirs_to_process(repo_root, mission_slug, json_output, errors) -> list[Path]`.
- **Files**: `src/specify_cli/cli/commands/materialize.py`, `tests/specify_cli/cli/commands/test_materialize.py`.
- **Validation**:
  - R24 is green; the lanes control is green.
  - Add `test_materialize_all_reports_remote_only_coord_mission_in_errors` (the loop continues, other Missions are processed).
  - Add `test_materialize_mission_flag_on_prefix_coord_mission_seeds_once`.
- **Edge cases**:
  - Mission dirs without `meta.json` (legacy): keep today's behaviour.
  - The derived dir `.kittify/derived` stays at the repository root checkout.
  - `MissionSelectorAmbiguous` rendering is unchanged.

### Subtask T102 – Guard sweep and resume-integrity record

- **Purpose**: Prove the terminus-integrity machinery (#5001) is untouched by the migration (research D21 "Guards that must stay green").
- **Steps**: run each named file, never the directory:
  - `tests/consolidation/test_single_rollback_authority.py` (AST-pinned rollback caller set) and `tests/consolidation/test_rollback_authority.py`
  - `tests/consolidation/test_reconciliation.py`, `test_reconciliation_divergent.py`, `test_squash_reconcilers_2709.py`
  - `tests/consolidation/test_bookkeeping_projection_seam.py`, `test_issue_2709_projection_union.py`, `test_projection_source_status_fallback_2709.py`
  - `tests/consolidation/test_done_bookkeeping_seam.py`, `test_done_bookkeeping_rollback_coherence.py`
  - `tests/consolidation/test_coord_deleted_degrade_paths.py`, `test_dry_run_fails_closed_on_unmaterialized_coord.py`, `test_executor_coord_reconcile.py`, `test_coord_teardown_order_3926.py`, `test_issue_4764_terminus_safety.py`
  - `tests/consolidation/test_canceled_content_residuals.py` (the strict `xfail`s must stay `xfail`; an XPASS is a failure to investigate, not a win)
  - `tests/cli/commands/test_merge_status_commit.py` (with the R23 re-pin)
  - `tests/coordination/test_projection_teardown.py` (WP17's refusal included)
  - `tests/specify_cli/cli/commands/test_materialize.py`
  - `tests/architectural/test_merge_reconciliation_class_guard.py`

  Record each command with pass/fail/xfail counts in the activity log.
  Then write a short **resume-integrity note** in the activity log: why the persisted `pre_mutation_refs`, `pre_mutation_coord_sha`, `pre_interrupt_lane_tips` and `reconciliation_passed_for_tip` are unaffected. A resumed run is MATERIALIZED or completed, so `write_dir` has no side effects (a pending seed commit, I-SEED-10, would already have been retried by the original run's unlocked pre-phase), and the completed case keeps PRIMARY via T100.
- **Validation**: all green; strict xfails unchanged.
- **Edge cases**: if a guard goes red, classify it first (baseline-red gotcha). If it is caused by this WP, fix the product; never re-pin a terminus guard to green-wash.

## Binding corrections — analyze + brownfield scout (round 3)

> These corrections are binding and **override any conflicting text earlier in this prompt**. Source: `analysis-report.md` and the brownfield scout notes (pointer in Context & Constraints). Operator decisions are quoted where they apply.

- **Extract before adding**: `_run_lane_based_consolidation` (L4114) is at **C901 14**. Its `seam.read_dir(STATUS_STATE)` is at **L4181**, with except arms at L4182-4194.
  - Adding the `CoordSeedForkRefused` and `FeatureStatusLockTimeoutError` arms would bring it to 16.
  - **First** extract `_resolve_run_status_dir(seam, …) -> Path` (raising `typer.Exit`) with focused tests, then add the arms there.
- **Locations**: `_phase_baseline_and_surface` is at **L799**; its `resolve_status_surface` call is at L825.
- **`materialize`** (`materialize.py` L40) is at **C901 15 (zero headroom)**. Extract the per-Mission dir resolution into a helper first. In the loop, keep the **root dir name** as the slug for `.kittify/derived/<slug>`, never the coordination path's name.
- **R23 remote-only control** needs a **new fixture**: a `file://` bare remote, the branch pushed, and the local head deleted. Keep only the assertions byte-for-byte.
- **PR-body note (operator decision)**: `consolidate --dry-run` stays fail-closed on UNMATERIALIZED (the forecast says abort), while the real run now materializes and proceeds. State this asymmetry in the PR body.
- **R22**: import WP03's seed-commit message constant; never hard-code the literal.
- **Merge lock**: verify that `_run_lane_based_consolidation` runs outside the global merge lock (the locked driver is `_run_lane_based_consolidation_locked` L3587; preflight-with-recovery L4029), and record the evidence.
- `test_canceled_content_residuals.py` uses strict xfail, so an XPASS is red.
- **C3**: the `consolidate` help says an UNMATERIALIZED coordination surface is materialized. The `materialize` help says the command may create coordination worktrees and seed them. Record the reference-doc delta for WP22.
- **P-M3**: consume `WriteLocation.checkout_root`; `executor.py` is in WP20's extended scan.

## Targeted test surface

- WP tests: `uv run --frozen pytest tests/consolidation/test_executor_coord_reconcile.py tests/consolidation/test_done_bookkeeping_seam.py tests/cli/commands/test_merge_status_commit.py tests/specify_cli/cli/commands/test_materialize.py -q`.
- The T102 guard list (named files only).
- Baseline: `make test-fast`.
- Named architectural gates:
  - `tests/architectural/test_merge_reconciliation_class_guard.py`
  - `tests/architectural/test_layer_rules.py`
  - `tests/architectural/test_status_state_read_dir_single_authority.py`
  - `tests/architectural/test_no_write_side_rederivation.py` (pre-extension; WP20 adds the census grammar that scans `executor.py::_phase_baseline_and_surface`, `::_run_lane_based_consolidation`, `materialize.py::_resolve_selected_dir` and `::materialize`, which must hold no read resolver for the write leg after this WP, except the documented completed-Mission read in T100)
- Never run the bare `tests/architectural/`, the whole `tests/consolidation/` directory, any e2e or integration directory, performance/stress suites, or `make test-full` (NO_FULL_HEAVY_SUITES_IN_MISSION, C-006).
- Record commands and counts for the PR's *Tests run* section. Classify unrelated reds per CLAUDE.md's baseline-red gotcha.

## Quality gates

- C901 ≤ 15 for every touched function (NFR-004). `_run_lane_based_consolidation` and `materialize` are long, so extract helpers rather than growing them.
- ruff check, ruff format --check, mypy --strict on changed files: 0 issues, no new suppressions (NFR-005).
- ≥ 90% coverage of new and changed lines, each new arm/helper with a focused test (NFR-003).

**WP20 note:** the completed-Mission `resolve_status_surface` call in T100 is a *read* of projected records. If WP20's grammar scans `_phase_baseline_and_surface`, isolate that read in a separately named helper (for example `_completed_mission_projected_events_path`) that is not on the census list, so the gate's allowlist can stay empty. Record this in the activity log for WP20.
- **Mission tracer files (analyze C4; charter Standing Order 3)**: at every decision point and every friction, append a dated entry through the canonical CLI, e.g. `spec-kitty agent tracer-append --mission coord-artifact-single-home-01M3V4BE --category design-decisions|approach|tooling-friction --entry "<YYYY-MM-DD WPxx: …>" --actor <you>`. The files are `traces/tooling-friction.md`, `traces/approach.md` and `traces/design-decisions.md`.
- **Pre-existing Failure Reporting Rule (analyze C4; charter)**: a red you did not cause and that is red on your base MUST be reported. Record the test id, the exact command and the evidence (output, base SHA) in the activity log and notify the orchestrator, who files the GitHub issue. Never fix it silently, never green-wash it, never xfail it.

## Issues

Issues: #5440 #5519

## Definition of Done

- R1d was committed first and is green throughout. R22, R23 (local) and R24 were red at base and are green at the end; R23 remote-only and the lanes controls are green.
- The executor's write location is `write_dir`, with three clean abort arms; the seed is before the merge lock and the snapshots.
- `_phase_baseline_and_surface` uses `run.feature_dir`, with the completed-resume exception preserved.
- `materialize` handles coordination Missions via `write_dir`, with per-Mission errors and help text updated.
- The T102 guard sweep is green, with counts recorded and the resume-integrity note written.
- Quality gates are clean.

## Risks & Mitigations

- **Deliberate behaviour change** (UNMATERIALIZED + local branch now proceeds): covered by the R23 split, with the rationale in the docstring and activity log.
- **Rollback/snapshot ordering**: a seed after the snapshot would be rolled back on FAIL. The R22 assertion that `pre_mutation_coord_sha` equals the seed commit pins it.
- **Dry-run side effects**: never call `write_dir` on the forecast path; `test_dry_run_fails_closed_on_unmaterialized_coord.py` guards it.
- **`done_marked_before_target` flip for pre-fix Missions**: expected per D21, and covered by R22 plus the done-bookkeeping guards.
- **`materialize` all-Missions cost**: one worktree per coordination Mission, created once. Mention it in the help text.

## Review Guidance

- The reviewer (opus, distinct from the implementer) verifies red→green: the R22/R23-local/R24 tests are RED on the WP's base and GREEN on the final commit, and R1d is green on both.
- Verify the commit order (R1d, then the red tests, then the fixes).
- Re-run at least `test_single_rollback_authority.py`, `test_done_bookkeeping_rollback_coherence.py` and `test_canceled_content_residuals.py` independently.
- Confirm the executor diff touches only `_run_lane_based_consolidation`'s surface resolution and arms, and `_phase_baseline_and_surface`.

## Activity Log

> **CRITICAL**: Activity log entries MUST be in chronological order (oldest first, newest last).

### How to Add Activity Log Entries

**When adding an entry**:

1. Scroll to the bottom of this Activity Log section
2. **APPEND the new entry at the END** (do NOT prepend or insert in middle)
3. Use exact format: `- YYYY-MM-DDTHH:MM:SSZ – agent_id – <action>`
4. Timestamp MUST be current time in UTC (check with `date -u "+%Y-%m-%dT%H:%M:%SZ"`)
5. Agent ID should identify who made the change (claude-sonnet-4-5, codex, etc.)

**Format**:

```
- YYYY-MM-DDTHH:MM:SSZ – <agent_id> – <brief action description>
```

**Common mistakes (DO NOT DO THIS)**:

- Adding new entry at the top (breaks chronological order)
- Using future timestamps (causes acceptance validation to fail)
- Inserting in middle instead of appending to end

**Initial entry**:

- 2026-10-01T08:36:27Z – system – Prompt created.

---

### Updating Status

Status is managed via `status.events.jsonl`. Use `spec-kitty agent tasks move-task <WPID> --to <status>` to change WP status.
- 2026-10-02T15:45:35Z – cursor – shell_pid=1212761 – WP18 evidence. R1d green at base (9f7e96dab0) and after. Red at base 9d0e98c3ab: R22 test_pre_fix_empty_coord_mission_records_done_on_coordination_surface (consolidation aborts in done bookkeeping, WP01=approved, because the EMPTY coord log reads genesis; the prompt's 'done lands in the root log' premise corrected), R23-local, R24-all, remote-only-errors, seeds-once. Green controls at base: R23 remote-only, R24 --mission (MATERIALIZED), lanes unchanged. R23 split is a DELIBERATE behaviour change under ruling Q4 (local-branch UNMATERIALIZED now materializes and proceeds). Fixes: 4379b8e864 executor (_resolve_run_status_dir via write_dir, 4 clean abort arms; _resolve_run_status_surface with completed-Mission exception isolated in _completed_mission_projected_events_path); 42d50da324 materialize. Merge lock evidence: _resolve_run_status_dir runs in _run_lane_based_consolidation BEFORE acquire_merge_lock and before _capture_pre_mutation_coord_checkpoint (called in the locked driver); R22 asserts pre_mutation_coord_sha == seed commit. C901: _run_lane_based_consolidation 14->12, materialize 15->14. Guard sweep (named files): rollback authority 41 passed; reconciliation trio 162 passed 1 xfailed; projection trio 19 passed; done-bookkeeping pair 45 passed; degrade/dry-run/coord_reconcile/teardown_3926/4764 28 passed; canceled_content_residuals 2 passed 5 xfailed (strict, no XPASS); merge_status_commit+projection_teardown+materialize+reconciliation_class_guard 49 passed; arch layer_rules+read_dir_single_authority+no_write_side_rederivation 114 passed; test-fast equivalent 2173 passed 5 skipped. RESUME-INTEGRITY NOTE: pre_mutation_refs, pre_mutation_coord_sha, pre_interrupt_lane_tips, reconciliation_passed_for_tip are persisted state never recaptured on --resume; a resumed run is MATERIALIZED or completed so write_dir has no side effects (a pending seed would have been retried by the original run's unlocked pre-phase), and the completed case keeps PRIMARY via _completed_mission_projected_events_path. PR-body note: consolidate --dry-run stays fail-closed on UNMATERIALIZED while the real run now materializes (UX asymmetry). WP20 note: the completed-Mission resolve_status_surface read is isolated in _completed_mission_projected_events_path (not on the census list). WP22 reference-doc delta (C3): consolidate help says an UNMATERIALIZED coordination surface is materialized; materialize help says it may create coordination worktrees and seed them. Gap: no named seed-subject constant in coord_seed.py (tracer tooling-friction). Not caused by this WP: executor.py mypy reports 6 pre-existing no-any-return errors at lines not touched.
