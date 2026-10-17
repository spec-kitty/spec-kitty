---
work_package_id: WP02
title: One meaning for an unclassified kind (predicate fix)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-012
- NFR-002
- NFR-004
- C-003
- C-004
- SC-004
planning_base_branch: fix/artifact-none-single-meaning
merge_target_branch: fix/artifact-none-single-meaning
branch_strategy: Planning artifacts for this mission were generated on fix/artifact-none-single-meaning. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/artifact-none-single-meaning unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-artifact-none-single-meaning-01M5365S
base_commit: 0d123d787e6af512ca8499997842aa11b3718213
created_at: '2026-10-17T05:17:55.344961+00:00'
subtasks:
- T007
- T008
- T009
- T010
- T011
- T012
phase: Phase 1 - One meaning for None
history:
- at: '{{TIMESTAMP}}'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/consolidation/
create_intent:
- tests/architectural/test_none_meaning_single_authority.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/consolidation/bookkeeping_projection.py
- src/specify_cli/cli/commands/agent/workflow.py
- tests/consolidation/test_projection_excludes_plan_outputs.py
- tests/consolidation/test_git_probes_git_paths.py
- tests/specify_cli/cli/commands/agent/test_partition_paths_by_primary_kind.py
- tests/architectural/test_none_meaning_single_authority.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – One meaning for an unclassified kind (predicate fix)

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter (`python-pedro`) before parsing the rest of this prompt, and behave according to its guidance.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Make an unclassified mission-artifact kind (`kind_for_mission_file(...) → None`)
mean exactly one thing — "not a coordination record" — across every consumer, by
routing the two dissenters through the single canonical authority
`coordination.coherence.is_coordination_kind_file`. Done when:

- `bookkeeping_projection._post_checkpoint_mission_paths` projects a mission path
  **iff** `is_coordination_kind_file(<mission-relative tail>)` is true — so a `None`
  path is never projected — while keeping the existing status/`meta.json` basename
  skip and the `{ISSUE_MATRIX, ACCEPTANCE_MATRIX}` exclusion.
- `workflow._partition_paths_by_primary_kind` routes a `None` path to
  `primary_bound` (via the same authority), matching the write-side placement.
- The #5697 regression repro (byte-identical unclassified `research/**`) is RED
  before the fix and GREEN after, through the pre-existing entry points.
- Coordination carry-forward is preserved (`traces/`, `decisions.events.jsonl`,
  review-cycle still projected) — the one selection-pinning assertion stays green.
- An architectural guard proves zero local `None → coord` re-derivations remain.
- No new suppression; complexity ≤ 15.

Requirements: FR-001, FR-002, FR-012, NFR-002, NFR-004, C-003, C-004, SC-004.

## Context & Constraints

- The one authority: `src/specify_cli/coordination/coherence.py::is_coordination_kind_file(relpath)` — "classifies to a known kind that is NOT primary". `None → not-coord → False`. Already shared by `coord_seed`, `coordination_alias_files`, `reconciliation`. **Reference it; do not fork or re-implement it.** It takes a mission-relative path; see its existing call sites for how to pass the mission-relative tail.
- Dissenter 1 (the #5697 refuse site): `src/specify_cli/consolidation/bookkeeping_projection.py::_post_checkpoint_mission_paths` (~662–729). Today: a `None` kind that is not `meta.json` stays projected. The diff: replace the "exclude known PRIMARY + meta, project the rest" denylist with a positive "project iff coordination-kind" rule, keeping the two status byte-sets + `meta.json` basename skip and the `{ISSUE_MATRIX, ACCEPTANCE_MATRIX}` exclusion (those are coord kinds with their own preservation paths and must NOT be projected here).
- Dissenter 2: `src/specify_cli/cli/commands/agent/workflow.py::_partition_paths_by_primary_kind` (393–418). Today: `None → coord_bound`. The diff: a path is `coord_bound` iff `is_coordination_kind_file` is true, else `primary_bound` (so `None → primary_bound`).
- Independent of WP01 (the predicate needs no new kind; `research/**` classifies to `None` on current main and to `RESEARCH` after WP01 — either way it is not a coordination kind, so it is never projected).
- Do NOT touch the related #5847 window (C-001). This WP changes only the None-meaning, not the projection window boundaries.

## Branch Strategy

- **Strategy**: {{branch_strategy}}
- **Planning base branch**: {{planning_base_branch}}
- **Merge target branch**: {{merge_target_branch}}

> Populated by `finalize-tasks`. Execution worktrees are allocated per lane from `lanes.json`.

## Subtasks & Detailed Guidance

### Subtask T007 – Red-first repro: projection refuses byte-identical unclassified research/** (FR-001/FR-012)

- **Purpose**: witness the #5697 refuse before fixing it.
- **Steps**: extend `tests/consolidation/test_projection_excludes_plan_outputs.py` with an issue-pinned `@pytest.mark.regression` test (ref `#5697`) shaped like the verified run: a mission with byte-identical unclassified `research/evidence.py` (and `research/notes.md`) on `coord` and the target, absent from the checkpoint, plus `traces/approach.md` as the coordination positive control. Assert, through the pre-existing entry points, that BEFORE the fix `_post_checkpoint_mission_paths` includes the `research/**` paths and `projected_content_matches_target` REFUSEs. Run it and capture the RED.
- **Files**: `tests/consolidation/test_projection_excludes_plan_outputs.py`.
- **Validation**: the test is RED on the pre-fix tree for the documented reason.

### Subtask T008 – Flip the `_partition_paths_by_primary_kind` contract (FR-002, intentional reversal)

- **Purpose**: witness dissenter 2 AND flip the existing tested contract as the honest red-first evidence.
- **Context**: `_partition_paths_by_primary_kind` has a DEDICATED test file, `tests/specify_cli/cli/commands/agent/test_partition_paths_by_primary_kind.py`, that currently PINS the pre-fix `None → coord_bound` behaviour as intended (the function docstring at `workflow.py` even documents it "preserving this sink's pre-fix behaviour"). WP02 intentionally REVERSES that to `None → primary_bound` to unify with the #2533 write-side authority (repo-root `meta.json`/config already route PRIMARY on the write side). This is a rationale'd contract flip, NOT a silent test edit.
- **Steps**:
  - In `tests/specify_cli/cli/commands/agent/test_partition_paths_by_primary_kind.py`, flip the three assertions that pin `None → coord_bound` to expect `primary_bound`: `test_non_mission_path_defaults_to_coord_bound` (repo-root `meta.json`), `test_other_missions_primary_artifact_is_not_primary_bound` (wrong-slug None path), and the `root_meta` case in `test_mixed_paths_are_split_and_keep_input_order`. Rename/retarget as needed so the test names describe the NEW contract; add a `#5697` rationale comment at the top explaining the intentional reversal. Keep the non-vacuous pairing: `status.events.jsonl` must still be `coord_bound` and a known-primary path still `primary_bound`.
  - Add the complementary assertion in `tests/consolidation/test_projection_excludes_plan_outputs.py` (the existing `_partition_paths_by_primary_kind` test) that an UNCLASSIFIED mission path is `primary_bound`.
  - Run RED first (the flipped assertions fail on the pre-fix tree), capture it, then GREEN after T010.
- **Files**: `tests/specify_cli/cli/commands/agent/test_partition_paths_by_primary_kind.py`, `tests/consolidation/test_projection_excludes_plan_outputs.py`.
- **Validation**: RED before T010, GREEN after; the reversal is documented, not greenwashed.

### Subtask T009 – Route the projection through is_coordination_kind_file

- **Purpose**: the load-bearing fix.
- **Steps**: in `_post_checkpoint_mission_paths`, change the per-path decision to: keep the `mission_prefix` scope and the status/`meta.json` basename skip; then include a path in the projected set **iff** `is_coordination_kind_file(<mission-relative tail>)` is true AND its kind is not in `{ISSUE_MATRIX, ACCEPTANCE_MATRIX}`. Import `is_coordination_kind_file` from `specify_cli.coordination.coherence`. Remove the old "`None` (not meta) stays projected" branch and the now-redundant PRIMARY denylist. Update the function docstring to state the one-meaning rule and that `None → not projected`.
  - **PATH FORM (critical — the loop does NOT currently strip to a tail).** The current loop only tests `candidate.startswith(mission_prefix)` and appends the FULL `candidate` (`kitty-specs/<slug>/…`) to `paths` — that full form is the function's return contract (consumed as `run.main_repo / rel`). `is_coordination_kind_file` expects the MISSION-RELATIVE TAIL (it internally composes `kitty-specs/_mission_/<tail>`; see `coherence.py` and the existing callers `reconciliation.py` `"/".join(parts[2:])`, `coordination_alias_files` `str(tracked)[len(prefix):]`). So you must ADD `relpath = candidate[len(mission_prefix):]`, pass THAT tail to `is_coordination_kind_file`, and keep appending the full `candidate`. Passing the full path instead makes `is_coordination_kind_file` compose `kitty-specs/_mission_/kitty-specs/<slug>/…` → keys on `"kitty-specs"` → returns False for everything → `traces/` silently stops projecting (an NFR-004 regression). Mirror `reconciliation.py` / `coordination_alias_files` exactly.
- **Files**: `src/specify_cli/consolidation/bookkeeping_projection.py`.
- **Validation**: T007's regression test turns GREEN; keep complexity ≤ 15 (extract a small predicate helper if needed).

### Subtask T010 – Route the workflow partition through is_coordination_kind_file

- **Purpose**: align dissenter 2 with the write side.
- **Steps**: in `_partition_paths_by_primary_kind`, classify each path as `coord_bound` iff `is_coordination_kind_file(<mission-relative tail>)` is true, else `primary_bound`. Update the docstring (the current one explicitly says `None → coord`; it must now say `None → primary_bound`, matching the #2533 write-side authority). Keep the function's return shape.
- **Files**: `src/specify_cli/cli/commands/agent/workflow.py`.
- **Validation**: T008's test turns GREEN; `status.events.jsonl` still `coord_bound`; a known-primary path still `primary_bound`.

### Subtask T011 – Verify carry-forward (NFR-004) + demote transitional repros

- **Purpose**: prove no coordination bookkeeping stopped being carried, and keep the suite honest.
- **Steps**:
  - Confirm the existing selection-pinning assertion (`_post_checkpoint_mission_paths(...) == [traces/approach.md]`) is still GREEN, and add/confirm cases that `decisions.events.jsonl` and `tasks/<wp>/review-cycle-*.md` still project (they classify to coord kinds).
  - **Retarget the `test_git_probes_git_paths.py` projected-path fixture (a second break test WP02 owns).** `tests/consolidation/test_git_probes_git_paths.py` (~lines 270–282) currently pins `_post_checkpoint_mission_paths` PROJECTING `notes/*` (`kitty-specs/m1/notes/é note.md`, `two words.md`). `notes/` classifies to `None` and is NOT classified by WP01, so after the predicate fix it is correctly NOT projected (it is a primary-surface working dir, never coord-authored — the same bug class as `research/`). The test's real purpose is to exercise unicode/space path handling through the projection probe, so RETARGET its fixture paths from `notes/*` to a projected COORD kind (`traces/é note.md`, `traces/two words.md`) and keep the assertion. Add a `#5697` comment: `notes/` is intentionally no longer projected. Do NOT delete the test.
  - Per the transitional-repro rule (ADR 2026-07-17-1): after the fix, the T007 repro becomes the permanent regression proof. Keep the `@pytest.mark.regression` + `#5697` pin (this is a defect-closing repro that should stay), but ensure it also reads as a focused behavioural assertion, not scaffolding.
- **Files**: `tests/consolidation/test_projection_excludes_plan_outputs.py`, `tests/consolidation/test_git_probes_git_paths.py`.
- **Validation**: `.venv/bin/python -m pytest tests/consolidation/test_projection_excludes_plan_outputs.py tests/consolidation/test_git_probes_git_paths.py tests/consolidation/test_bookkeeping_projection_seam.py tests/specify_cli/cli/commands/agent/test_partition_paths_by_primary_kind.py -q` green.

### Subtask T012 – NFR-002 architectural guard: no local None→coord re-derivation

- **Purpose**: close the parallel-authority class by construction (Standing Order #5 — non-vacuous gate).
- **Steps**: create `tests/architectural/test_none_meaning_single_authority.py`. The guard must be non-vacuous (a concrete floor + self-mutation sensitivity). A good shape: AST-scan `bookkeeping_projection._post_checkpoint_mission_paths` and `workflow._partition_paths_by_primary_kind` to assert each (a) references `is_coordination_kind_file`, and (b) contains no `is None` branch that appends to a coord/projected bucket. Include a self-check that the floor set is exactly those two functions (so deleting a function from the floor fails the test). Keep it in `tests/architectural/` but it runs as a normal fast test here (do not run the whole `tests/architectural/` dir — per `NO_FULL_HEAVY_SUITES_IN_MISSION`, run only this file).
- **Files**: `tests/architectural/test_none_meaning_single_authority.py`.
- **Validation**: `.venv/bin/python -m pytest tests/architectural/test_none_meaning_single_authority.py -q` green; it goes RED if either consumer reverts to a local `None → coord` branch.

## Test Strategy

Red-first per ADR 2026-07-17-1 (C-004). Run only the owned/affected tests
foreground: `.venv/bin/python -m pytest tests/consolidation/test_projection_excludes_plan_outputs.py tests/consolidation/test_git_probes_git_paths.py tests/consolidation/test_bookkeeping_projection_seam.py tests/specify_cli/cli/commands/agent/test_partition_paths_by_primary_kind.py tests/architectural/test_none_meaning_single_authority.py -q`. The orchestrator runs the wider blast radius (`tests/consolidation/`, `tests/coordination/`, `tests/specify_cli/`).

## Definition of Done

- T007–T012 complete; the #5697 repro RED→GREEN captured in history.
- Both consumers consume `is_coordination_kind_file`; no local `None → coord` branch remains (guard green).
- Carry-forward preserved (NFR-004); existing selection assertion green.
- `ruff check` + `ruff format --check --force-exclude` clean on the four owned files.
- No suppression added; complexity ≤ 15.

## Risks & Reviewer Guidance

- **Reviewer**: confirm the projection still skips the status pair + `meta.json` and still excludes `{ISSUE_MATRIX, ACCEPTANCE_MATRIX}` (regression: those have their own preservation path and must not be double-projected). Confirm `traces/`/`decisions.events.jsonl`/review-cycle still project. Confirm the guard is non-vacuous (mutate one consumer locally and watch it go red). Confirm #5847's window boundaries are untouched (C-001).
- **Risk**: passing the wrong path form to `is_coordination_kind_file` (it expects a mission-relative tail, not the full `kitty-specs/<slug>/...`). The loop does NOT strip to a tail today — you must add `relpath = candidate[len(mission_prefix):]` and keep appending the full `candidate` (see T009). Mirror `reconciliation.py` / `coordination_alias_files`.
