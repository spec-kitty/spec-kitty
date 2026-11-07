---
work_package_id: WP14
title: S7 settlement at the first finalize, with compensation
dependencies:
- WP06
- WP12
- WP13
- WP15
requirement_refs:
- FR-053
- FR-054
- FR-055
- FR-056
- FR-057
- FR-058
- FR-061
- SC-007
- NFR-002
- NFR-003
- C-010
- C-011
planning_base_branch: issue-7276-lane-worktree-hardening
merge_target_branch: issue-7276-lane-worktree-hardening
branch_strategy: Planning artifacts for this mission were generated on issue-7276-lane-worktree-hardening. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7276-lane-worktree-hardening unless the human explicitly redirects the landing branch.
subtasks:
- T082
- T083
- T084
- T085
- T086
- T087
- T088
- T089
- T090
phase: Phase 5 - S7 topology settled at finalize
history:
- at: '2026-11-06T08:51:52Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/lanes/
create_intent:
- src/specify_cli/lanes/topology_settlement.py
- tests/specify_cli/cli/commands/agent/test_finalize_topology_settlement.py
- tests/lanes/test_topology_settlement_compensation.py
- tests/integration/test_default_mission_primary_placement.py
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/agent/mission_finalize.py
- src/specify_cli/cli/commands/agent/mission_finalize_lanes.py
- src/specify_cli/cli/commands/agent/mission_finalize_commit.py
- src/specify_cli/lanes/topology_settlement.py
- src/specify_cli/cli/commands/agent/tasks_finalize.py
- src/specify_cli/migration/mission_state.py
- tests/specify_cli/cli/commands/agent/test_finalize_topology_settlement.py
- tests/lanes/test_topology_settlement_compensation.py
- tests/integration/test_default_mission_primary_placement.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP14 - S7 settlement at the first finalize, with compensation

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `implementer-ivan`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log. Address every item; record progress with `spec-kitty agent tasks add-history WP14 --note "..."`.

---

## Implementation command

```bash
cd /home/user/spec-kitty
spec-kitty agent action implement WP14 --agent claude --mission lane-worktree-model-hardening-01M6QY1M
```

## Objectives & Success Criteria

S7 (#7282), settlement half. The first `finalize-tasks` of a provisional Mission (`topology_source: default`, `topology_settled: false`) settles once, before finalize's first status write and before any WP is claimed:

- FR-053 size rule: `single_branch` when <= 2 non-canceled WPs (planning-artifact WPs count) or <= 1 code lane; else `lanes_with_coord` on any target with the topic branch as the coordination branch (DM `01M6R0B954ZPQN5NV4R1ZRE7NY`). Tie 2 WPs/2 lanes -> `single_branch`; 0 code lanes -> `single_branch`.
- FR-054 / C-011: never re-decide (re-finalize, legacy `tasks-finalize` repair, doctor rebuilds); growth keeps the settled topology.
- FR-055: `single_branch` = no git step. `lanes_with_coord` = (1) commit the Mission dir on the topic branch in the write checkout; (2) move the repository root checkout to `create_return_branch`; (3) re-stamp `meta.json` (`coordination_branch` = topic ref, `mission_branch` kept as PRIMARY, `topology: lanes_with_coord`, `topology_settled: true`, `topology_decision`); (4) materialize the coordination worktree on the topic branch (`CoordinationWorkspace.resolve()`); (5) write `lanes.json`. No planning commit on the target; no lane branches/checkouts (A-7). Every pre-settlement planning artifact and status event stays readable.
- FR-056 / NFR-003: refuses `WRITE_CHECKOUT_OCCUPIED` / `WRITE_CHECKOUT_DIRTY` / `TOPOLOGY_SETTLEMENT_REFUSED`; any failure leaves the Mission provisional with `meta.json` byte-identical, branch tips unchanged, no coordination worktree, root checkout back on the topic branch.
- FR-057: Missions with no `topology_source` are settled and never change.
- FR-058: `--validate-only` previews the decision and writes nothing; `--json` reports `topology_decision` per `contracts/finalize-tasks-json.md`; `orchestrator-api tasks` passes it through (contract 1.24.0; WP15 owns the bump and documents `topology_decision`, this WP depends on WP15 and does not edit `envelope.py` or `docs/api/orchestrator-api.md`, analysis F2).
- FR-061 (DM `01M6R0QJVPVZG2QT8MWQD4NXJR`): a default Mission's PRIMARY reads/writes go to the topic branch before and after settlement. The `consolidate` landing of those artifacts on the target is WP20 (FR-062, analysis E1), not this WP. Explicit `--topology` keeps PRIMARY on `target_branch`. `spec-kitty agent context resolve --json` (`mission_dir`) and `check-prerequisites --paths-only` return the PRIMARY-partition location after settlement too.
- SC-007 finalize half; NFR-002 (no lost events across settlement).

## Context & Constraints

- Read: spec User Story 3, FR-050 to FR-061, Edge Cases (settlement interrupted, create from another branch, tie, canceled WPs, `--pr-bound`); `research.md` R-6 (the 5-step path, compensation preconditions); `data-model.md` §1 (keys, state machine); `contracts/finalize-tasks-json.md`; `contracts/error-codes.yaml`; WP02 ADR; WP13's keys, switch core, `count_code_lanes`, `restamp_*` helper.
- **C-010**: S8 (WP11/WP12) must ship with this. Depends on WP12.
- **#7255 (NOT merged, `issue-7210-finalize-derived-pin`)** touches finalize-tasks: rebase your finalize phases after it lands.
- `src/mission_runtime/resolution.py` is owned by WP06; your provisional / default-PRIMARY arm of `single_branch_write_ref` (`:1056`) is an out-of-map hunk sequenced after WP06. Keep it pure (no `specify_cli` import): pass `topology_source` in.
- Complexity Tracking (plan): settlement's git operations sit outside `StatusSurfaceGuard`; its own compensation and the fault-injection test cover that.
- Destructive ops (removing a half-materialized coordination worktree during compensation) go through `git/destructive_guard.py` (C-004) if that module offers the primitive on the topic branch at implementation time; otherwise use the existing guarded coordination teardown primitive. No raw `worktree remove --force`.
- Insertion points: `_decide_topology_by_size` before the frozen preflight (`mission_finalize.py:~1449`); `_apply_topology_settlement` before `_emit_tasks_started` (`:~1462`).
- C-011 red-first.

## Branch Strategy

- **Strategy**: Planning artifacts were generated on issue-7276-lane-worktree-hardening; completed changes must merge back into issue-7276-lane-worktree-hardening.
- **Planning base branch**: issue-7276-lane-worktree-hardening
- **Merge target branch**: issue-7276-lane-worktree-hardening

## Subtasks & Detailed Guidance

### Subtask T082 - First commit: PRIMARY placement pin

- `tests/integration/test_default_mission_primary_placement.py`:
  - `test_default_mission_primary_placement_topic_branch_pinned`: a default Mission's spec/plan/tasks/WP files/`lanes.json`/`meta.json` are read and written on the topic branch before and after settlement (both outcomes). The `consolidate` landing leg is WP20's (FR-062); do not assert it here.
  - Positive control: explicit `--topology lanes_with_coord` keeps PRIMARY on `target_branch`.
  - `test_context_resolve_and_prerequisites_report_primary_location_after_settlement`: after a `lanes_with_coord` settlement (root checkout back on `create_return_branch`), `spec-kitty agent context resolve --action implement --mission <h> --json` `mission_dir` and `spec-kitty agent mission check-prerequisites --json --paths-only --mission <h>` return the PRIMARY-partition location (not the root checkout's copy).
- Commit first (red where not yet implemented).

### Subtask T083 - Red-first settlement scenarios

`tests/specify_cli/cli/commands/agent/test_finalize_topology_settlement.py`:

- `test_two_wp_settles_single_branch_events_readable`
- `test_three_lanes_protected_settles_lanes_with_coord_topic_is_coord`
- `test_three_lanes_unprotected_settles_lanes_with_coord_topic_is_coord` (no commit on target; lanes later fork from the topic branch)
- `test_settlement_moves_root_checkout_before_coord_worktree`
- `test_settlement_refuses_missing_or_busy_return_branch`
- `test_explicit_lanes_and_coord_still_materialize_at_create` (positive control)
- `test_five_wp_one_code_lane_settles_single_branch`
- `test_explicit_topology_wins`
- `test_refinalize_never_redecides`
- `test_legacy_mission_without_source_never_changes` (with a provisional control in the same fixture)
- `test_canceled_wps_not_counted_planning_wps_counted`

### Subtask T084 - Red-first preview, report, refusal, fault injection

- `test_validate_only_previews_and_writes_nothing` (hash the Mission dir and refs)
- `test_finalize_json_reports_decision` (also via `orchestrator-api tasks`)
- `test_settlement_refuses_occupied_or_dirty_write_checkout`
- `tests/lanes/test_topology_settlement_compensation.py::test_settlement_fault_injection_restores_byte_identical`: parametrize one arm per git step (commit, root checkout move, meta re-stamp, coordination worktree materialize, lanes.json write); inject failure; assert `meta.json` byte-identical, all branch tips unchanged, no coordination worktree, root checkout on the topic branch, Mission provisional (NFR-003, 100% of points).

### Subtask T085 - Decision phase

- `_decide_topology_by_size(mission) -> TopologyDecision | None`: None when already settled (explicit, owned, legacy, or `topology_settled: true`). Count non-canceled WPs from the reduced status + WP files; code lanes via `count_code_lanes` on the computed lanes. Return `{rule, wp_count, code_lane_count, from, to, target_protected}` (rule values `wp_count_le_2 | code_lanes_le_1 | lanes_with_coord`). Preconditions: no WP past `planned`, no lane branch/worktree recorded.

### Subtask T086 - `lanes/topology_settlement.py`

- A plan of reversible steps with an undo stack: `SettlementStep(apply, undo, name)`. Execute in order; on exception run undos in reverse, then raise `TopologySettlementRefused` (`TOPOLOGY_SETTLEMENT_REFUSED`) with the remedy (name the return branch when relevant). Preconditions checked before step 1 (write checkout clean/unoccupied via WP13's core; `create_return_branch` exists and is not checked out elsewhere).
- Snapshot `meta.json` bytes and branch tips before step 1 for byte-identical restore.
- Each function <= 15 complexity.

### Subtask T087 - Finalize wiring

- `mission_finalize.py`: call the decision before the frozen preflight; call `_apply_topology_settlement` before `_emit_tasks_started`; `--validate-only` returns the preview only.
- `mission_finalize_lanes.py`: takes the decided topology (lanes computed for the settled topology).
- `mission_finalize_commit.py`: the re-stamped `meta.json` is attributable in the finalize commit (commits land on the topic/coordination branch, never the target).
- JSON: `topology_decision` with `preview` / `settled_this_run` flags.

### Subtask T088 - `resolution.py` provisional arm (out-of-map, after WP06)

- `single_branch_write_ref` (and its repository-reading wrapper) route PRIMARY writes of a `topology_source: default` Mission to `mission_branch` also after settlement to `lanes_with_coord`. Pure function: add a parameter for the source. Record the out-of-map hunk.

### Subtask T089 - No-redecide pins [P]

- `tasks_finalize.py` (legacy repair path) and `migration/mission_state.py` (doctor rebuild): never call the decision; add a guard + assertion and a short test in the T083 file.

### Subtask T090 - Quality gates and blast radius

See Validation.

## Validation

```bash
cd <workspace>
uv run --frozen pytest tests/integration/test_default_mission_primary_placement.py tests/specify_cli/cli/commands/agent/test_finalize_topology_settlement.py tests/lanes/test_topology_settlement_compensation.py -q
uv run --frozen pytest tests/specify_cli/cli/commands/agent -q -n auto --dist loadfile -k "finalize or tasks"   # out-of-matrix dir
uv run --frozen pytest tests/lanes tests/mission_runtime tests/migration tests/coordination tests/orchestrator_api tests/specify_cli/orchestrator_api -q -n auto --dist loadfile
uv run --frozen pytest tests/contract/test_orchestrator_api.py tests/architectural/test_layer_rules.py tests/architectural/test_read_surface_placement_guard.py -q
make test-fast
uv run --frozen ruff check <touched> && uv run --frozen ruff format --check --force-exclude <touched>
uv run --frozen mypy --strict <touched src files>
```

Never `make test-full` or a bare `tests/architectural/` sweep.

## Tracer files

Return tracer lines in your completion summary (`- **[YYYY-MM-DD][implement WP14] ...**`, naming the trace file); the orchestrator appends them.

## Risks & Mitigations

- Git forbids one branch in two worktrees: step 2 precedes step 4 (test).
- Half-materialized coordination worktree: undo through a guarded primitive.
- This WP is large (9 subtasks): if a session cannot finish, stop after T087 with green tests and report; the orchestrator may split T088-T089.

## Review Guidance

- Decide once; one settlement path; fault injection covers every step; nothing lands on the target; PRIMARY pinned on the topic branch; resolver-path tests present.

## Definition of Done

- T082-T090 done; tests green; tracer lines returned.

## Progress & Status

- `spec-kitty agent tasks mark-status T082 T083 T084 T085 T086 T087 T088 T089 T090 --status done --mission lane-worktree-model-hardening-01M6QY1M`
- `spec-kitty agent tasks move-task WP14 --to for_review --mission lane-worktree-model-hardening-01M6QY1M`
