---
work_package_id: WP20
title: "S7: consolidate lands a default Mission's PRIMARY artifacts from the topic branch"
dependencies:
- WP07
- WP14
- WP15
requirement_refs:
- FR-055
- FR-061
- FR-062
- SC-007
- NFR-002
planning_base_branch: issue-7276-lane-worktree-hardening
merge_target_branch: issue-7276-lane-worktree-hardening
branch_strategy: Planning artifacts for this mission were generated on issue-7276-lane-worktree-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7276-lane-worktree-hardening unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-lane-worktree-model-hardening-01M6QY1M
base_commit: a4e342649cfe4936e89b4da0e8599dffc658ace2
created_at: '2026-11-06T21:43:01.518997+00:00'
subtasks:
- T118
- T119
- T120
- T121
- T122
- T123
phase: Phase 5 - S7 topology settled at finalize
history:
- at: '2026-11-06T10:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.analyze remediation (finding E1)
- at: '2026-11-06T12:00:00Z'
  actor: system
  action: Re-aimed via /spec-kitty.analyze re-run 2 remediation (findings G1-G5, G8)
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- tests/consolidation/test_topic_branch_primary_landing.py
- tests/integration/test_default_mission_consolidate_lands_primary.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/bookkeeping_projection.py
- tests/consolidation/test_topic_branch_primary_landing.py
- tests/integration/test_default_mission_consolidate_lands_primary.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP20 - S7: consolidate lands a default Mission's PRIMARY artifacts from the topic branch

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission lane-worktree-model-hardening-01M6QY1M`). Feedback items are your TODO list. Record progress with `spec-kitty agent tasks add-history WP20 --note "..."`.

---

## Implementation command

```bash
cd /home/user/spec-kitty
spec-kitty agent action implement WP20 --agent claude --mission lane-worktree-model-hardening-01M6QY1M
```

Work in the workspace the command prints.

## Objectives & Success Criteria

S7 (#7282), the consolidate leg of the default-Mission placement (plan IC-18; analysis E1, re-aimed by re-run 2 findings G1-G4 and G8, each verified against the code):

- **FR-062**: `consolidate` of a `topology_source: default` Mission settled to `lanes_with_coord` leaves no PRIMARY-partition change of its topic branch off `target_branch` when the coordination teardown deletes that branch. The topic branch is the coordination branch and the `lanes.json` `mission_branch` (one name, `kitty/mission-<slug>-<mid8>`). `_PRIMARY_ARTIFACT_KINDS` in `src/mission_runtime/artifacts.py`: spec, plan, research, data-model, contracts, tasks, WP files, `lanes.json`, `meta.json`.
- **The real window (G1)**: `consolidation/phase_advance.py::_phase_mission_to_target` already squashes the topic branch's tip onto the target through `lanes/consolidation.py::integrate_mission_into_target` (the `meta.json` driver runs two-way there; target-authoritative fields stay the target's). A PRIMARY edit made after the last lane cut but before `consolidate` therefore already lands. The window that is dropped is PRIMARY commits on the topic branch after the consolidation checkpoint (`phase_claim.py`, `run.coord_checkpoint`) that the landing did not carry: made after the landing read the tip, up to the coordination teardown, including the resumed late window (`phase_teardown.py`). `bookkeeping_projection.py::_post_checkpoint_mission_paths` excludes PRIMARY kinds on purpose. T118 confirms or refutes this before any implementation.
- **Mid-run PRIMARY reads (G4)**: consolidate reads `meta.json` / `lanes.json` through `run.target_feature_dir` (`executor.py:446`, `phase_advance.py:319-321` baseline id) and detects coordination topology from `coordination_branch` in the target `meta.json` (`run_state.py::_is_coord_topology_mission`). For a default Mission those files are on the topic branch until the landing. Before the landing these reads resolve the Mission's PRIMARY anchor; after it, the target. The post-teardown phases (`mission_number` bake, baseline stamp, retrospective, the landed-state clears) find them on the target.
- **Target-authored values survive (G2)**: the `mission_number` bake and the `baseline_merge_commit` stamp the run commits on the target are never overwritten by a stale copy from the topic/coordination ref.
- **FR-055 / FR-061**: lanes are cut from the topic branch, lane consolidation lands into it, and it lands on the target at consolidate (operator OQ-2: "cut the lanes from it and consolidate into it"; DM `01M6R0QJVPVZG2QT8MWQD4NXJR`).
- **NFR-002**: no status event and no PRIMARY change is lost across `--resume` or a rollback.
- **SC-007** (consolidate half): after `consolidate`, 100% of the topic branch's PRIMARY changes are on the target.
- **Control**: an explicit `--topology lanes_with_coord` Mission consolidates exactly as today (byte-identical target tree for the same fixture).
- If T118 shows nothing is lost in any window, this WP reduces to the pinning tests (T119) and the mid-run read fix (G4) only; record that and do not add code for the landing window.

## Context & Constraints

- Read: spec FR-055, FR-061, FR-062, SC-007, Topology Lifecycle; plan IC-14 and IC-18; `research.md` R-6; the WP02 ADR `2026-11-06-3`; CLAUDE.md "Consolidation & Preflight Patterns" (rollback authority, `CoordMovedAfterLanding`, `ProjectionTeardownGate`, approved-claim axes).
- **Phase order** (`executor.py`): `_phase_gates_and_state` (checkpoint, `phase_claim.py`) -> `_phase_merge_lanes` -> `_phase_baseline_and_surface` -> `_phase_bake_and_pre_target_done` -> `_phase_mission_to_target` (the landing) -> `_phase_capture_and_baseline` -> `_phase_record_done_and_project` (`project_post_checkpoint_commits_to_target`, coordination records only) -> ... -> `_phase_reconcile_before_teardown` -> `_phase_cleanup_worktrees_and_branches` (coordination teardown, late window).
- **One landing authority (charter: single canonical authority)**: the landing seam is `_phase_mission_to_target` / `integrate_mission_into_target`. Do NOT add a parallel landing path. **Never widen `project_post_checkpoint_commits_to_target` / `_post_checkpoint_mission_paths` to PRIMARY kinds** (G2): the coordination ref carries stale pre-merge copies, and projecting them clobbers the target's `mission_number` bake and `baseline_merge_commit` stamp (the guard's documented "WP10 integration fix" regression; `meta.json` also stays excluded for the #5460 two-way reason).
- **Separate predicate (G3)**: the default-Mission landing decision is a NEW predicate (for example `lands_topic_branch(repo, manifest)`) in `lanes/single_branch_landing.py`, keyed on the STORED `topology_source` + topology in `meta.json` (WP13's `meta_keys.py`), never on a derived or manifest-only fact. `lands_mission_branch` is unchanged, so its six `single_branch` callers keep their behaviour: `executor.py:456` and `:953` (`planning_artifact_only`), `phase_advance.py:328` (`done_marked_before_target`) and `:582` (checkout switch), `phase_teardown.py:792` and `:850` (`mission_branch` clear and delete).
- **Rollback**: `consolidation/rollback.py::rollback_to_snapshot` stays the one restore authority (AST pin `tests/consolidation/test_single_rollback_authority.py`). Any new ref advance goes through `git/ref_advance.py::advance_branch_ref` (compare-and-swap) inside the recorded span. A refusal reuses the existing teardown codes (`PROJECTION_TEARDOWN_ABORTED`, `COORD_MOVED_AFTER_LANDING` exit 75); no new error code (C-012).
- **Approved-claim and gate axes**: PRIMARY paths under `kitty-specs/<slug>/` are bookkeeping for the gate (`_is_bookkeeping`); check the blob-attribution, closed-world and approved-bound axes do not refuse the landed PRIMARY change, and do not widen any axis to make a test pass. If an axis refuses, stop and record it as a design question.
- **`test_projection_excludes_plan_outputs.py`**: it pins the exclusion. Keep it green; it is the guard G2 relies on.
- **Recorded out-of-map edits** (one-line rationale each in the completion summary; each owner WP is a dependency, directly or transitively, and each owner prompt names this hunk):
  - `src/specify_cli/lanes/single_branch_landing.py` (owned by WP11; WP20 -> WP14 -> WP12 -> WP11): the new default-Mission predicate, on top of WP11's write-branch collapse. `lands_mission_branch` unchanged.
  - `src/specify_cli/consolidation/phase_advance.py` (owned by WP07): the landing-phase call or check, and the pre-landing `target_feature_dir` read in `_phase_baseline_and_surface`.
  - `src/specify_cli/consolidation/phase_teardown.py` (owned by WP15): land-before-coordination-teardown check; keep WP15's order coordination -> lanes -> record clear and the S10 exit codes (1 / 75).
  - `src/specify_cli/consolidation/run_state.py` (owned by WP15): `_is_coord_topology_mission` for a default Mission whose `meta.json` is still on the topic branch.
  - `src/specify_cli/consolidation/executor.py` (owned by WP15): the `target_feature_dir` PRIMARY anchor (`executor.py:446`) for a default Mission. Do not touch the `lands_mission_branch` calls at `:456` / `:953`.
  - `src/specify_cli/orchestrator_api/consolidation.py` (owned by WP15), ONLY if `test_primary_landing_through_orchestrator_api` cannot pass by pinning current behaviour (G8). Prefer pinning; if a hunk is needed, keep it to the same predicate and anchor calls, and add no error code.
- Layering: `mission_runtime` must not import `specify_cli` (`tests/architectural/test_layer_rules.py`).
- C-011 red-first: tests committed BEFORE the implementation commit, red on **WP20's own lane base** (after WP07, WP14 and WP15 have landed into it), never on the planning base: the fixture needs WP14's settlement, so red on the planning base would be vacuous. Never retry-to-green.
- C-010: this WP ships with WP13 and WP14 (same release).

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-7276-lane-worktree-hardening; completed changes must merge back into issue-7276-lane-worktree-hardening.
- **Planning base branch**: issue-7276-lane-worktree-hardening
- **Merge target branch**: issue-7276-lane-worktree-hardening

> Execution worktrees are allocated per computed lane from `lanes.json`.

## Subtasks & Detailed Guidance

### Subtask T118 - Characterization test that decides the design (commit first)

- Write it as a committed test (`tests/integration/test_default_mission_consolidate_lands_primary.py::test_characterize_default_mission_primary_windows`), on WP20's lane base, on a real git fixture (reuse `tests/integration/coord_topology_fixture.py` and WP14's settlement helpers): create without `--topology`, finalize to `lanes_with_coord` (3 code lanes), implement and approve the WPs.
- Window A (control for the premise): edit `tasks/WP01-*.md`, `spec.md` and an additive `meta.json` key on the topic branch after the last lane cut, before `consolidate`. Expected: already on the target after consolidate (the landing carries the tip). Pin it.
- Window B (the suspected gap): commit the same kinds of edit on the topic branch after the checkpoint and after `_phase_mission_to_target` read the tip, before the coordination teardown (inject through a test hook at the phase boundary, and again in the resumed late window). Record whether they reach the target or are dropped, and which function drops them (`_post_checkpoint_mission_paths` vs teardown).
- Window C (G4): record what `run.target_feature_dir`, `run.baseline_mission_id` and `_is_coord_topology_mission(run)` resolve to before and after the landing for the default Mission, and whether the coordination triple is torn down and `mission_number` baked on the target.
- The test asserts today's observed behaviour; put the finding in the completion summary (tracer line). It decides T121: if Window B loses nothing and Window C is correct, T120/T121 reduce to pins.

### Subtask T119 - Red-first acceptance tests (commit before T120/T121)

`tests/integration/test_default_mission_consolidate_lands_primary.py` (through the real `spec-kitty consolidate` CLI on real git fixtures):

- `test_primary_commit_after_landing_before_teardown_reaches_target_or_refuses` (Window B): such a commit is on the target after `consolidate`, or the teardown refuses through its existing path with the coordination branch kept; never silently deleted.
- `test_target_authored_mission_number_and_baseline_survive` (G2): after a default-Mission consolidate with a post-checkpoint `meta.json` commit on the topic branch, the target's `meta.json` carries the run's `mission_number` and `baseline_merge_commit`, not the topic branch's stale values.
- `test_default_mission_consolidate_detects_coord_topology_and_bakes_on_target` (G4): coordination topology is detected, the coordination triple (branch, worktree, marker) is torn down, `mission_number` is baked on the target, and `baseline_mission_id` is the Mission's id.
- `test_resume_and_rollback_lose_no_primary_change`: (1) inject a failure between the landing and the coordination teardown, then `consolidate --resume` completes and the target carries every change; (2) force a gate FAIL so the run rolls back through `rollback_to_snapshot`: the target is restored, the topic branch still carries every PRIMARY change, and a second run lands them. No new restore path (the AST pin stays green).
- `test_explicit_lanes_with_coord_consolidate_unchanged` (control): explicit `--topology lanes_with_coord` on the same fixture shape gives today's target tree and today's output.
- `test_primary_landing_through_orchestrator_api` (G8): `orchestrator-api consolidate-mission` lands the same PRIMARY changes (parity with the CLI), or, if that path has no rollback door for it, refuses with its existing `PREFLIGHT_FAILED` envelope and the test pins that (no new error code; C-012). Prefer a pin of current behaviour; a hunk in `orchestrator_api/consolidation.py` is a recorded out-of-map edit (WP15).

`tests/consolidation/test_topic_branch_primary_landing.py` (unit level):

- `test_lands_topic_branch_default_lanes_with_coord_true`, `test_lands_topic_branch_explicit_lanes_with_coord_false`, `test_lands_topic_branch_legacy_mission_false` (no `topology_source`: FR-057 control), `test_lands_mission_branch_unchanged_for_default_mission` (the existing predicate returns what it returns today for every topology, so its six callers are unchanged).
- `test_post_checkpoint_projection_still_excludes_primary_kinds` (G2: the guard is not widened).

Each must be red on WP20's lane base (the predicate cases may be red only for the new predicate; the unchanged-predicate and exclusion pins are green controls; record which).

### Subtask T120 - Separate default-Mission predicate (recorded out-of-map edit)

- In `lanes/single_branch_landing.py`, add `lands_topic_branch(repo, manifest)` (name may differ) beside `lands_mission_branch`. Read `topology_source` and the stored topology from `meta.json` through the existing readers (`meta_keys.py` keys from WP13). Do not change `lands_mission_branch` or any of its six callers.

### Subtask T121 - Close the window T118 shows; fix the mid-run PRIMARY reads

- Window B: either (preferred) refuse the coordination teardown while a PRIMARY change on the topic branch is not on the target, through the existing `ProjectionTeardownGate` / `PROJECTION_TEARDOWN_ABORTED` / `CoordMovedAfterLanding` paths (`phase_teardown.py`, out-of-map), or re-land through `integrate_mission_into_target` inside the recorded span (`@_records_post_mutation_tips`, `advance_branch_ref`). A pure helper in `bookkeeping_projection.py` (owned) may compute "PRIMARY paths on the topic branch not on the target" for that check, comparing against the checkpoint so target-authored `meta.json` fields are never overwritten. Do NOT widen `project_post_checkpoint_commits_to_target`.
- Window C: make `run.target_feature_dir` (`executor.py`, out-of-map, WP15) and `_is_coord_topology_mission` (`run_state.py`, out-of-map, WP15) resolve the Mission's PRIMARY anchor before the landing for a default Mission (gated on `lands_topic_branch`), and the target after it; adjust the pre-landing baseline read in `phase_advance.py` (out-of-map, WP07) if T118 shows it reads the wrong surface.
- Keep each function at complexity <= 15; extract pure helpers (path selection, change detection) and test them directly.

### Subtask T122 - Make the red tests green; confirm the control

- Run T119's tests; all green. Run `test_projection_excludes_plan_outputs.py`, `test_late_teardown_projection.py`, `test_bookkeeping_projection_seam.py`, `test_single_rollback_authority.py`: green (or a recorded, red-first flip for default Missions only).

### Subtask T123 - Quality gates and blast radius

See Validation.

## Validation

```bash
cd <workspace>
uv run --frozen pytest tests/integration/test_default_mission_consolidate_lands_primary.py tests/consolidation/test_topic_branch_primary_landing.py -q
uv run --frozen pytest tests/consolidation/test_projection_excludes_plan_outputs.py tests/consolidation/test_late_teardown_projection.py tests/consolidation/test_bookkeeping_projection_seam.py tests/consolidation/test_issue_2709_projection_union.py tests/consolidation/test_projection_source_status_fallback_2709.py tests/consolidation/test_single_rollback_authority.py -q
uv run --frozen pytest tests/consolidation tests/lanes tests/specify_cli/consolidation tests/orchestrator_api tests/specify_cli/orchestrator_api tests/integration/test_default_mission_primary_placement.py -q -n auto --dist loadfile
uv run --frozen pytest tests/specify_cli/cli/commands -q -n auto --dist loadfile -k "consolidate"   # out-of-matrix dir
uv run --frozen pytest tests/architectural/test_layer_rules.py tests/architectural/test_destructive_op_routing.py -q
make test-fast
uv run --frozen ruff check <touched> && uv run --frozen ruff format --check --force-exclude <touched>
uv run --frozen mypy --strict <touched src files>
```

- Complexity <= 15 per function. No new `# noqa` / `# type: ignore`. Repeated literals (>= 3) become constants.
- NEVER run `make test-full` or a bare `tests/architectural/` sweep (`NO_FULL_HEAVY_SUITES_IN_MISSION`).
- Classify unrelated reds per CLAUDE.md "baseline-red gotcha" before touching them.

## Tracer files

Code WPs must not change Mission files from a lane worktree. Return tracer lines in your completion summary, formatted `- **[YYYY-MM-DD][implement WP20] <finding>.** <detail>. Disposition: <...>.`, naming the target file (`kitty-specs/lane-worktree-model-hardening-01M6QY1M/traces/approach.md`, `.../design-decisions.md` or `.../tooling-friction.md`). Include T118's characterization result and each out-of-map hunk with its rationale.

## Risks & Mitigations

- A parallel landing path appears: review rejects anything that does not go through `_phase_mission_to_target` / `integrate_mission_into_target` and the recorded ref-advance span.
- The target's `mission_number` / `baseline_merge_commit` is clobbered: `test_target_authored_mission_number_and_baseline_survive` and the unwidened exclusion pin catch it.
- The approved-claim axes refuse the landed PRIMARY commit: stop and record; never widen an axis to pass.
- Explicit Missions change behaviour: the control test (c) and the explicit-Mission projection pins catch it.
- Out-of-map conflicts with WP07/WP11/WP15: this WP depends on all three (WP11 transitively), so it rebases onto their final shape.

## Review Guidance

- Red-first commits precede the implementation commit (`git log --oneline`).
- One landing authority; rollback unchanged; no new error code; S10 exit codes unchanged.
- T118's characterization test is the first commit and its finding is reported; red tests were red on WP20's lane base, not the planning base.
- `lands_mission_branch` is byte-unchanged; `project_post_checkpoint_commits_to_target` is not widened to PRIMARY kinds.
- Out-of-map hunks in `single_branch_landing.py`, `phase_advance.py`, `phase_teardown.py`, `run_state.py`, `executor.py` (and `orchestrator_api/consolidation.py` only if needed) are small and listed with rationale.
- mypy/ruff/format clean on touched files.

## Definition of Done

- T118-T123 done; all targeted tests green; out-of-map hunks listed with rationale; tracer lines returned.

## Progress & Status

- `spec-kitty agent tasks mark-status T118 T119 T120 T121 T122 T123 --status done --mission lane-worktree-model-hardening-01M6QY1M`
- `spec-kitty agent tasks move-task WP20 --to for_review --mission lane-worktree-model-hardening-01M6QY1M`
