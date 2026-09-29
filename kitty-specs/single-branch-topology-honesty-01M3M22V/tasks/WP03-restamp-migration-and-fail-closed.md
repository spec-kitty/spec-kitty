---
work_package_id: WP03
title: Topology reader counts code lanes; fail closed; re-stamp migration; doctor
dependencies:
- WP02
requirement_refs:
- FR-014
- FR-015
- FR-016
- FR-017
- NFR-003
planning_base_branch: issue-5100-single-branch-topology
merge_target_branch: issue-5100-single-branch-topology
branch_strategy: Planning artifacts for this mission were generated on issue-5100-single-branch-topology. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5100-single-branch-topology unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-single-branch-topology-honesty-01M3M22V
base_commit: b1d397061491858776902e2ea97355cb3d50457d
created_at: '2026-09-28T17:49:36.793298+00:00'
subtasks:
- T010
- T011
- T012
- T013
- T014
- T015
phase: Phase 2 - Topology authority
history:
- at: '2026-09-28T14:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/migration/
create_intent:
- src/specify_cli/upgrade/migrations/m_4_0_0rc5_single_branch_code_lanes_restamp.py
- tests/specify_cli/upgrade/migrations/test_single_branch_code_lanes_restamp.py
- tests/lanes/test_code_lane_predicates.py
- tests/mission_runtime/test_assert_topology_matches_manifest.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/lanes/compute_and_persist.py
- src/specify_cli/migration/backfill_topology.py
- src/specify_cli/migration/mission_state.py
- src/mission_runtime/context.py
- src/specify_cli/upgrade/migrations/m_4_0_0rc5_single_branch_code_lanes_restamp.py
- src/specify_cli/cli/commands/_identity_audit.py
- src/specify_cli/cli/commands/migrate_cmd.py
- src/specify_cli/cli/commands/agent/tasks_finalize.py
- tests/specify_cli/upgrade/migrations/test_single_branch_code_lanes_restamp.py
- tests/lanes/test_code_lane_predicates.py
- tests/mission_runtime/test_assert_topology_matches_manifest.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – Topology reader counts code lanes; fail closed; re-stamp migration; doctor

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter (`python-pedro`, role `implementer`, agent `claude`), and behave according to its guidance before parsing the rest of this prompt.

---

## ⚠️ IMPORTANT: Review Feedback

Check the event log for `review_ref`. Address every item before finishing.

---

## Objectives & Success Criteria

This WP implements decision item 3 and the lane-presence rule (FR-014, FR-015, FR-016, FR-017):

1. **Predicates.** Three predicates in `src/specify_cli/lanes/compute.py`, next to `is_planning_lane` / `is_planning_artifact_only`:
   - `is_repo_root_lane(lane)`: today it has the same backing as `is_planning_lane`; keep `is_planning_lane` as the existing name and make `is_repo_root_lane` the new canonical name used by new code;
   - `has_code_lanes(manifest)`;
   - `has_code_wps(manifest, wp_kinds)`.

   `is_planning_artifact_only` stays **lane-based and unchanged** (plan fold B3).
2. **Derivation.** `backfill_topology._has_lanes` counts **code lanes only**, which covers `read_topology`, `classify_from_meta` and backfill.
3. **Fail-closed check.** `assert_topology_matches_manifest(topology, manifest)` in `src/mission_runtime/context.py` raises `SINGLE_BRANCH_CODE_LANES_UNMIGRATED` when `topology is SINGLE_BRANCH` and the manifest has code lanes. It is called at the two writer chokepoints:
   - in `compute_and_persist` after `:170`, before the write at `:172`;
   - at the top of `allocate_lane_worktree`.
4. **Topology parameter.** `compute_and_write_lanes` takes `topology` explicitly from all three callers:
   - `tasks_finalize.py:382`;
   - `mission_finalize.py:2503` (out-of-map, rationale);
   - `migration/mission_state.py:1621`. `doctor mission-state --fix` must catch the new error and report it rather than crash.
5. **Migration.** A re-stamp migration plus operator CLI, and a doctor finding.

**Done when**:
- the red-first migration test is committed RED first and is now GREEN;
- the predicates and the assertion have focused tests;
- the doctor reports the finding;
- a dry-run against this repository's `kitty-specs/` reports exactly the missions to re-stamp (64 at mission start).

## Context & Constraints

- Read first: `plan.md` IC-02 and the folds (B3, M3, and the minor about the planning-only reclassification control); `research.md` R-3, R-4; `contracts/topology-restamp.md`; `data-model.md`.
- **No runtime fallback (C-003).** Never make `read_topology` or any read path raise or reinterpret. Status, accept and doctor reads must keep working for unmigrated missions. Only the two *writers* fail closed.
- **Migration shape.** Mirror `src/specify_cli/upgrade/migrations/m_4_0_0rc5_heal_template_set_provenance.py:328-345`:
  - `MIGRATION_ID = "4_0_0rc5_single_branch_code_lanes_restamp"`;
  - `TARGET_VERSION = "4.0.0rc5"`;
  - `runs_on_worktrees = False`.

  It writes meta through the canonical meta writer (`_write_meta_canonical`, or whatever `backfill_topology` already uses). It changes only `topology`, and **it does not commit**: the upgrade auto-commit owns that.
- **Out-of-map edits.** Each needs a one-line rationale in the Activity Log:
  - `src/specify_cli/lanes/compute.py` (predicates; WP05 owns the file);
  - `src/specify_cli/lanes/worktree_allocator.py` (one assertion call; WP07 owns it);
  - `src/specify_cli/cli/commands/agent/mission_finalize.py` (topology argument);
  - `src/specify_cli/cli/commands/doctor.py`, if the finding needs wiring there.
- **T015 data commit.** The in-repo `kitty-specs/*/meta.json` re-stamp is NOT made in this WP; code_change WPs may not own `kitty-specs/`. The orchestrator makes that commit at wrap-up by running the migration. Here you only produce the dry-run evidence.

## Branch Strategy

- **Planning base / merge target**: `issue-5100-single-branch-topology`.
- Workspace: run `spec-kitty implement WP03 --mission single-branch-topology-honesty-01M3M22V`.

## Subtasks & Detailed Guidance

### Subtask T010 – Red-first migration test (commit FIRST, alone)

- **File**: `tests/specify_cli/upgrade/migrations/test_single_branch_code_lanes_restamp.py`, marked `@pytest.mark.regression`.
- **Tests**:
  1. `test_migration_registered`: `MigrationRegistry.get_by_id("4_0_0rc5_single_branch_code_lanes_restamp") is not None`. Use a registry lookup, **not** an import, so the red is an assertion. Follow the pattern in `tests/**/test_heal_template_set_provenance.py`.
  2. `test_restamps_only_code_lane_missions_idempotent`: build three missions in a tmp `kitty-specs/`:
     - (a) `single_branch` with `lanes.json` containing a code lane `lane-a` → re-stamped to `lanes`, and every other meta key is byte-identical;
     - (b) `single_branch` with only a `lane-planning` lane → unchanged;
     - (c) `single_branch` with no `lanes.json` → unchanged.

     Run the migration twice and assert the files are byte-identical after the second run (NFR-003).
  3. (moved to WP05 T022 — post-tasks fold B-2: the fail-closed call sites land together with the single_branch `compute_lanes` arm, otherwise every single_branch finalize goes red between WP03 and WP05.)
  4. `test_planning_only_unstamped_mission_classification_unchanged`: control for the `has_code_lanes` change. A meta without `topology` and with a planning-only manifest derives the same topology before and after.
- Commit this test alone: `test(migration): red-first single_branch code-lane re-stamp`.

### Subtask T011 – Predicates

- In `lanes/compute.py`:
  - `is_repo_root_lane(lane: ExecutionLane) -> bool` returns `lane.lane_id == PLANNING_LANE_ID` (same backing as `is_planning_lane`).
  - `has_code_lanes(manifest: LanesManifest) -> bool` returns `any(not is_repo_root_lane(l) for l in manifest.lanes)`.
  - `has_code_wps(manifest, kinds: Mapping[str, WorkProductKind]) -> bool`: true when any WP in the manifest is `code_change`. Read the kinds through the existing normalized WP index; do not re-parse frontmatter.
- In `migration/backfill_topology.py:52-60`, `_has_lanes` delegates to `has_code_lanes`.
- Tests go in `tests/lanes/test_code_lane_predicates.py`: every predicate, true and false cases.

### Subtask T012 – Fail-closed assertion and topology parameter

- `mission_runtime/context.py`:
  - add the pure `assert_topology_matches_manifest(topology: MissionTopology, *, has_code_lanes: bool, mission_slug: str) -> None`. Pass a bool, not the manifest type, so `mission_runtime` does not import `specify_cli` (layer rules: `specify_cli` depends on `mission_runtime`, never the reverse);
  - raise a new `TopologyManifestMismatch` (a `StructuredError`-style error with `error_code = "SINGLE_BRANCH_CODE_LANES_UNMIGRATED"`) whose message names the mission and the remedy (`spec-kitty upgrade` or `spec-kitty migrate backfill-topology --restamp-single-branch`);
  - export it in `__all__`, and make sure `tests/architectural/test_no_dead_symbols.py` is satisfied by real callers.
- `compute_and_write_lanes(..., topology: MissionTopology)`: thread the parameter through from all three callers now, but **do not call the assertion yet** — WP05 T022 inserts both call sites (this one and `allocate_lane_worktree`) in the same commit as the single_branch `compute_lanes` arm (post-tasks fold B-2).
- `migration/mission_state.py:1621`: catch `TopologyManifestMismatch` and report it as a finding (no crash). Test: monkeypatch `compute_and_write_lanes` to raise it and assert `doctor mission-state --fix` reports the finding and exits cleanly (name the test in the Activity Log).
- Tests go in `tests/mission_runtime/test_assert_topology_matches_manifest.py`.

### Subtask T013 – Re-stamp function, migration and CLI

- `backfill_topology.restamp_single_branch_with_code_lanes(repo_root, *, dry_run: bool) -> RestampResult`. It walks `kitty-specs/*/`, selects missions per `contracts/topology-restamp.md`, and writes `topology: lanes` only. Follow the `TopologyBackfillResult` style.
- Migration module: `detect()` returns true if any mission is selectable, and `apply()` calls the function.
- `migrate_cmd.py:574`: add `--restamp-single-branch` (plus `--dry-run`) to `backfill-topology`.

### Subtask T014 – Doctor topology finding

- `_identity_audit.run_topology_audit` (`:329`): add a per-row `finding` field. Emit `SINGLE_BRANCH_CODE_LANES_UNMIGRATED` for affected missions, and nothing for clean single_branch missions (negative control).
- Tests: extend `tests/doctor/test_identity_audit.py` / `tests/specify_cli/cli/commands/test_identity_audit.py` with a positive and a negative case.

### Subtask T015 – Dry-run evidence (data commit deferred to wrap-up)

- Run `spec-kitty migrate backfill-topology --restamp-single-branch --dry-run` against this repository.
- Paste the count, and the first five slugs, into the Activity Log. The expected count is 64 (± any mission merged since).
- Do **not** commit changes under `kitty-specs/`.

## Test Strategy

```bash
.venv/bin/python -m pytest tests/specify_cli/upgrade/migrations/test_single_branch_code_lanes_restamp.py tests/lanes/test_code_lane_predicates.py tests/mission_runtime/test_assert_topology_matches_manifest.py -q
.venv/bin/python -m pytest tests/specify_cli/migration/test_backfill_topology.py tests/specify_cli/migration/test_backfill_topology_mission_scope.py tests/migration/test_backfill_topology_cli.py tests/doctor/test_identity_audit.py tests/specify_cli/cli/commands/test_identity_audit.py -q
grep -rl "compute_and_write_lanes\|read_topology\|classify_from_meta\|is_planning_artifact_only" tests/ --include=*.py   # run each listed file
.venv/bin/python -m pytest tests/architectural/test_layer_rules.py tests/architectural/test_no_dead_symbols.py -q
.venv/bin/mypy --strict src/specify_cli/migration/ src/mission_runtime/context.py src/specify_cli/lanes/ ; .venv/bin/ruff check . ; .venv/bin/ruff format --check .
```

## Risks & Mitigations

- **Layer rules.** `mission_runtime` must not import `specify_cli`. That is why the assertion takes a bool; `test_layer_rules.py` pins it.
- **Reclassifying legacy missions.** The T010 control test pins that nothing is reclassified.
- **`doctor mission-state --fix` crash.** It must catch the new error; add a test.

## Review Guidance

- Verify red→green for T010.
- Confirm there is no read-path fail-closed (C-003).
- Confirm the migration writes `topology` only and does not commit.
- Confirm the T015 evidence is present.

## Activity Log

- 2026-09-28T14:00:00Z – system – Prompt created.
