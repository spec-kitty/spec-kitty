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

S7 (#7282), the consolidate leg of the default-Mission placement (plan IC-18, analysis finding E1):

- **FR-062**: `consolidate` of a `topology_source: default` Mission settled to `lanes_with_coord` carries every PRIMARY-partition change on the topic branch (= its coordination branch; `_PRIMARY_ARTIFACT_KINDS` in `src/mission_runtime/artifacts.py`: spec, plan, research, data-model, contracts, tasks, WP files, `lanes.json`, `meta.json`) onto `target_branch` BEFORE the coordination teardown deletes that branch. This includes PRIMARY edits made on the topic branch after the last lane was cut.
- **FR-055 / FR-061**: lanes are cut from the topic branch, lane consolidation lands into it, and it lands on the target at consolidate (operator OQ-2: "cut the lanes from it and consolidate into it"; DM `01M6R0QJVPVZG2QT8MWQD4NXJR`).
- **NFR-002**: no status event and no PRIMARY change is lost across `--resume` or a rollback.
- **SC-007** (consolidate half): after `consolidate`, 100% of the topic branch's PRIMARY changes are on the target.
- **Control**: an explicit `--topology lanes_with_coord` Mission consolidates exactly as today (byte-identical target tree for the same fixture).

## Context & Constraints

- Read: spec FR-055, FR-061, FR-062, SC-007, Topology Lifecycle; plan IC-14 and IC-18; `research.md` R-6; the WP02 ADR `2026-11-06-3`; CLAUDE.md "Consolidation & Preflight Patterns" (rollback authority, `CoordMovedAfterLanding`, `ProjectionTeardownGate`, approved-claim axes).
- **Today's gap**: only a protected `single_branch` Mission lands its `mission_branch` (`src/specify_cli/lanes/single_branch_landing.py::lands_mission_branch`, called from `consolidation/phase_advance.py`, `executor.py` and `phase_teardown.py`). `consolidation/bookkeeping_projection.py` projects only status bookkeeping (`_project_status_bookkeeping_to_target`) and coordination commits made after the checkpoint (`project_post_checkpoint_commits_to_target`); `tests/consolidation/test_projection_excludes_plan_outputs.py` pins that plan outputs are excluded today. Then coordination teardown deletes the coordination branch.
- **One landing authority (charter: single canonical authority)**: extend the existing mission-branch landing seam; do NOT add a parallel landing path. The predicate keys on the STORED `topology_source` + topology in `meta.json`, never on a derived or manifest-only fact (a coord Mission's `mission_branch` is its coordination branch; an explicit `lanes_with_coord` Mission must keep today's behaviour).
- **Rollback**: `consolidation/rollback.py::rollback_to_snapshot` stays the one restore authority (AST pin `tests/consolidation/test_single_rollback_authority.py`). Any new ref advance goes through `git/ref_advance.py::advance_branch_ref` (compare-and-swap) inside the recorded span so the existing snapshot/post-tip bookkeeping covers it.
- **Approved-claim and gate axes**: PRIMARY paths under `kitty-specs/<slug>/` are bookkeeping for the gate (`_is_bookkeeping`); check the blob-attribution, closed-world and approved-bound axes do not refuse the landed PRIMARY change, and do not widen any axis to make a test pass. If an axis refuses, stop and record it as a design question.
- **`test_projection_excludes_plan_outputs.py`**: it pins the exclusion for explicit Missions. Keep it green for explicit Missions; if a case must change for default Missions, flip it in a separate red-first commit and say why.
- **Recorded out-of-map edits** (one-line rationale each in the completion summary; the owner WPs are dependencies, directly or transitively):
  - `src/specify_cli/lanes/single_branch_landing.py` (owned by WP11; WP20 -> WP14 -> WP12 -> WP11): the default-settled `lanes_with_coord` arm of the landing predicate, on top of WP11's write-branch collapse.
  - `src/specify_cli/consolidation/phase_advance.py` (owned by WP07, a dependency): the call that lands the topic branch's PRIMARY changes in the mission-to-target phase.
  - `src/specify_cli/consolidation/phase_teardown.py` (owned by WP15, a dependency): land-before-coordination-teardown ordering; keep WP15's order coordination -> lanes -> record clear and the S10 exit codes (1 / 75).
- Layering: `mission_runtime` must not import `specify_cli` (`tests/architectural/test_layer_rules.py`).
- C-011 red-first: tests committed BEFORE the implementation commit, red on the planning base. Never retry-to-green.
- C-010: this WP ships with WP13 and WP14 (same release).

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-7276-lane-worktree-hardening; completed changes must merge back into issue-7276-lane-worktree-hardening.
- **Planning base branch**: issue-7276-lane-worktree-hardening
- **Merge target branch**: issue-7276-lane-worktree-hardening

> Execution worktrees are allocated per computed lane from `lanes.json`.

## Subtasks & Detailed Guidance

### Subtask T118 - Characterize today's consolidate of a default `lanes_with_coord` Mission

- On a real git fixture (reuse `tests/integration/coord_topology_fixture.py` and WP14's settlement helpers): create without `--topology`, finalize to `lanes_with_coord` (3 code lanes), implement and approve the WPs, edit `tasks/WP01-*.md`, `spec.md` and `meta.json` (an additive key) on the topic branch after the last lane is cut, then run `spec-kitty consolidate`.
- Record which PRIMARY paths reach the target and which are lost, and which function drops them (projection vs teardown). Put the finding in the completion summary (tracer line); it decides T121's exact hook.

### Subtask T119 - Red-first acceptance tests (commit before T120/T121)

`tests/integration/test_default_mission_consolidate_lands_primary.py` (through the real `spec-kitty consolidate` CLI on real git fixtures):

- `test_primary_edit_after_last_lane_cut_reaches_target` (a): every PRIMARY change on the topic branch, including those made after the last lane cut, is on the target after `consolidate`; the coordination branch is torn down afterwards as today.
- `test_resume_and_rollback_lose_no_primary_change` (b): (1) inject a failure between the PRIMARY landing and the coordination teardown, then `consolidate --resume` completes and the target carries every change; (2) force a gate FAIL so the run rolls back through `rollback_to_snapshot`: the target is restored, the topic branch still carries every PRIMARY change, and a second run lands them. No new restore path (the AST pin stays green).
- `test_explicit_lanes_with_coord_consolidate_unchanged` (c, control): explicit `--topology lanes_with_coord` on the same fixture shape gives today's target tree and today's output.
- `test_primary_landing_through_orchestrator_api`: `orchestrator-api consolidate-mission` lands the same PRIMARY changes (parity with the CLI), or, if that path has no rollback door for it, refuses with its existing `PREFLIGHT_FAILED` envelope and the test pins that (no new error code; C-012).

`tests/consolidation/test_topic_branch_primary_landing.py` (unit level):

- `test_landing_predicate_default_lanes_with_coord_true`, `test_landing_predicate_explicit_lanes_with_coord_false`, `test_landing_predicate_legacy_mission_false` (no `topology_source`: FR-057 control), `test_landing_predicate_single_branch_unchanged`.
- `test_projection_carries_primary_kinds_only` (status bookkeeping keeps its own projection; non-PRIMARY paths are never carried by the new leg).

Each must be red on the planning base (the predicate cases may be red only for the default arm; record which).

### Subtask T120 - Extend the landing predicate (recorded out-of-map edit)

- In `lanes/single_branch_landing.py`, add the default-settled `lanes_with_coord` arm to the landing decision (for example a `lands_topic_branch_primary(repo, manifest)` beside `lands_mission_branch`, or one predicate returning the landing kind). Read `topology_source` and the stored topology from `meta.json` through the existing readers (`meta_keys.py` keys from WP13). Keep `lands_mission_branch` callers' behaviour for `single_branch` unchanged.

### Subtask T121 - Land the topic branch's PRIMARY changes before coordination teardown

- `consolidation/bookkeeping_projection.py` (owned): a PRIMARY-partition projection leg (or a widened `project_post_checkpoint_commits_to_target` limited to `_PRIMARY_ARTIFACT_KINDS` for default Missions) that carries the topic branch's PRIMARY changes onto the target as one attributable commit, idempotent on `--resume` (a second run finds nothing to carry).
- `consolidation/phase_advance.py` (out-of-map): call it in the mission-to-target phase, inside the recorded span (`@_records_post_mutation_tips`), through `advance_branch_ref`.
- `consolidation/phase_teardown.py` (out-of-map): assert the landing happened (or was a no-op) before `ProjectionTeardownGate` and the coordination triple teardown; never delete the coordination branch while a PRIMARY change on it is not on the target (refuse with the existing `PROJECTION_TEARDOWN_ABORTED` path, no new code).
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

- A parallel landing path appears: review rejects anything that does not go through the extended landing predicate and the recorded ref-advance span.
- The approved-claim axes refuse the landed PRIMARY commit: stop and record; never widen an axis to pass.
- Explicit Missions change behaviour: the control test (c) and the explicit-Mission projection pins catch it.
- Out-of-map conflicts with WP07/WP11/WP15: this WP depends on all three (WP11 transitively), so it rebases onto their final shape.

## Review Guidance

- Red-first commits precede the implementation commit (`git log --oneline`); each red test was red on the planning base.
- One landing authority; rollback unchanged; no new error code; S10 exit codes unchanged.
- Out-of-map hunks in `single_branch_landing.py`, `phase_advance.py`, `phase_teardown.py` are small and listed with rationale.
- mypy/ruff/format clean on touched files.

## Definition of Done

- T118-T123 done; all targeted tests green; out-of-map hunks listed with rationale; tracer lines returned.

## Progress & Status

- `spec-kitty agent tasks mark-status T118 T119 T120 T121 T122 T123 --status done --mission lane-worktree-model-hardening-01M6QY1M`
- `spec-kitty agent tasks move-task WP20 --to for_review --mission lane-worktree-model-hardening-01M6QY1M`
