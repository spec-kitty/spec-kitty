---
description: "Work package task list for the tooling-friction fresh-env remediation mission"
---

# Work Packages: Tooling friction — fresh-env derived-state & partition remediation

**Inputs**: Design documents from `/kitty-specs/tooling-friction-fresh-env-remediation-01M3GN66/`
**Prerequisites**: plan.md (required), spec.md (user stories)

**Tests**: Every WP is a bugfix; each carries a red-first regression test (SC no-op-passable = no).

**Organization**: Subtasks (`Txxx`) roll up into work packages (`WPxx`). Each WP is independently deliverable and testable.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** indicates the subtask can proceed in parallel (different files/components).
- Record completion with `spec-kitty agent tasks mark-status <Txxx> --status done`.

## Path Conventions

- Single project: `src/`, `tests/`.

---

## Work Package WP01: Charter JSON contract test isolation (#4873) (Priority: P1) 🎯 MVP

**Goal**: The three charter JSON error-contract tests assert their intended contracts from any cwd, including an isolated linked worktree.
**Independent Test**: From `git worktree add` linked worktree, `PWHEADLESS=1 pytest tests/cli/commands/test_charter_json_error_contract.py -q` passes.
**Prompt**: `/tasks/WP01-charter-json-test-isolation.md`
**Requirement Refs**: FR-001, C-001

### Included Subtasks

T001 Reproduce the three failures from a linked worktree (red-first evidence).
T002 Add the `autouse` `_isolate_cwd_from_worktree_guard` fixture to `tests/cli/commands/test_charter_json_error_contract.py`, mirroring `tests/specify_cli/cli/commands/test_charter_resynthesize.py:21-35`.
T003 Verify green from both a linked worktree and a root checkout; confirm NO production file changed.

### Dependencies

- None.

### Risks & Mitigations

- Preserve the #4785 guard-before-`find_repo_root` invariant (C-001) — test-only change.

---

## Work Package WP02: Dev-dependency packaging mirror (#5160 friction 2) (Priority: P1)

**Goal**: A plain `uv sync` / `uv run --frozen` lane venv carries `pytestarch`; a guard fails closed if a needed test plugin is missing from the dev group.
**Independent Test**: `uv sync --frozen` (no extras) then `uv run --frozen python -c "import pytestarch"` exits 0.
**Prompt**: `/tasks/WP02-dev-dependency-mirror.md`
**Requirement Refs**: FR-002

### Included Subtasks

T004 Add `pytestarch>=4.0.0` to `[dependency-groups].dev` in `pyproject.toml`, mirroring the existing `pytest-xdist`/`pytest-timeout` entries (same pin as the `test` extra).
T005 Regenerate `uv.lock` (record it in the dev group) via `uv lock`.
T006 [P] Add a pyproject-shape assertion in `tests/architectural/test_pyproject_shape.py` that every plugin `make test-fast`/`test-full` needs without `--all-extras` (xdist, timeout, pytestarch) is present in the `dev` group.

### Dependencies

- None (cross-cutting: run `tests/architectural/` in full).

### Risks & Mitigations

- Keep the dev-group pin equal to the `test` extra to avoid `uv.lock` drift.

---

## Work Package WP03: Shared `status.json` re-materialization authority (Priority: P0)

**Goal**: One shared helper regenerates `status.json` from a union-merged event log, reused by lane allocation (WP04) and the squash seam (WP05).
**Independent Test**: Given a merged `status.events.jsonl`, the helper returns `materialize(reduce(union events))` and its callers reference the SAME helper (no second copy).
**Prompt**: `/tasks/WP03-shared-rematerialization-authority.md`
**Requirement Refs**: NFR-002

### Included Subtasks

T007 Extract/hoist a shared re-materialization entry from `src/specify_cli/merge/bookkeeping_projection.py::_rematerialize_status_snapshot` (reduce → materialize_to_json), keeping the T012 AST-lint-sanctioned write shape.
T008 [P] Unit-test the shared helper directly (union → reduce → snapshot equality).

### Dependencies

- None (foundational). Blocks WP04, WP05.

### Risks & Mitigations

- Do not fork the reduce/materialize logic; single authority (NFR-002).

---

## Work Package WP04: Lane-allocation derived-state regeneration (#5160 friction 1) (Priority: P1)

**Goal**: Lane allocation regenerates a conflicting derived `status.json` from the merged log instead of failing closed; genuine human-authored conflicts still block.
**Independent Test**: Two branches, divergent `status.json`, union-able event logs → `allocate_lane_worktree` (reuse/crash-recovery/fresh) completes; resulting snapshot equals `materialize(reduce(union))`. A `tasks/WP*.md` conflict still raises.
**Prompt**: `/tasks/WP04-lane-alloc-rematerialize.md`
**Requirement Refs**: FR-003

### Included Subtasks

T009 Red-first: allocation test with divergent derived `status.json` (currently raises `PlanningCommitMergeConflictError`/`DependencyLaneMergeConflictError`).
T010 In `_merge_recorded_planning_commit` and `_merge_dependency_lane_tips` (`lanes/worktree_allocator.py`), after the merge, resolve remaining-unmerged derived snapshots via the WP03 helper before the abort/raise.
T011 [P] Control test: a human-authored (`tasks/WP01.md`) conflict still fails closed (no green-washing); preserve the #4905 `wp_task_conflicts` diagnostic.

### Dependencies

- Depends on WP03.

### Risks & Mitigations

- Scope regeneration strictly to derived snapshots (`status.json`); never widen to human-authored paths.

---

## Work Package WP05: Squash-seam reconciliation, driver registry & C-006 guard (#4955) (Priority: P1)

**Goal**: The mission→target squash reconciles derived/append-only mission state; `mission-events.jsonl` gains a union driver across all four bound surfaces; `kitty-ops/lifecycle.jsonl` and `decisions/index.json` get an explicit reconciliation decision; the C-006 completeness guard leaves no artifact silently exempt.
**Independent Test**: A both-sides-divergent squash reconciles `status.json` (re-materialize) and `mission-events.jsonl` (union) without blocking; the guard enumerates/classifies every canonical artifact.
**Prompt**: `/tasks/WP05-squash-seam-reconciliation.md`
**Requirement Refs**: FR-004, FR-005, FR-006, FR-007, FR-008, NFR-001

### Included Subtasks

T012 Red-first: both-sides-divergent squash integration test proving `status.json`/`mission-events.jsonl` currently block.
T013 Add a post-squash re-materialize/re-fold hook in `lanes/merge.py::_merge_branch_into` (reuse WP03 helper for `status.json`; `_refold_decisions_index` via `decisions/index_fold.py::fold_events` if index.json is re-derived).
T014 Add `mission-events.jsonl` to `_MERGE_DRIVERS` reusing the `spec-kitty-event-log` driver; seed across `.gitattributes`, `cli/commands/init.py`, and a new `MergeDriverSeedingMigration` subclass.
T015 Add `mission-events.jsonl` to `_MISSION_FILE_KIND_BY_BASENAME` (`mission_runtime/artifacts.py`) so the guard enumerates it.
T016 Decide + implement `kitty-ops/lifecycle.jsonl` (bespoke union driver keyed by full-line identity, OR a documented block) and `decisions/index.json` (re-fold OR documented block); record the decision.
T017 Correct `tests/architectural/test_merge_reconciliation_class_guard.py`: reclassify so each artifact carries a driver or an explicit non-divergent/re-materialized classification — no silent exemption; keep the four `test_*_superset*`/`test_declared_*` guards green.
T018 [P] Driver unit tests + guard-completeness assertions.

### Dependencies

- Depends on WP03.

### Risks & Mitigations

- Four registration surfaces must stay in sync; guard classification is a decision — re-decide explicitly (CLAUDE.md tension noted).

---

## Work Package WP06: Planning-action `feature_dir` primary anchor (#5160 friction 3) (Priority: P2)

**Goal**: `context resolve --action tasks` and `check-prerequisites` return the same primary `feature_dir`; status actions still resolve the coord surface.
**Independent Test**: On a materialized coord mission, `context resolve --action tasks --json` `feature_dir` == `check-prerequisites --json` `FEATURE_DIR`; `--action status` still coord.
**Prompt**: `/tasks/WP06-planning-feature-dir-anchor.md`
**Requirement Refs**: FR-009

### Included Subtasks

T019 Red-first: surface-disagreement test on a coord-topology mission.
T020 In `resolve_action_context`/`_resolve_mission_slug` (`mission_runtime/resolution.py`), route planning-action `feature_dir` through the primary anchor (`_primary_anchored_feature_dir`/`primary_feature_dir_for_mission`), coord fallback only when no primary dir exists.
T021 [P] Regression: status/analyze/accept actions still resolve the coord status surface.

### Dependencies

- None.

### Risks & Mitigations

- Consider hoisting a shared primary-anchor authority so the two entry points cannot re-diverge (#2101 recurrence guard).

---

## Work Package WP07: Coordination-materialization remedy text (#5113, remedy-only) (Priority: P2)

**Goal**: The `CoordinationWorktreeUnmaterialized` remedy names a working `git worktree add` command; materialize-before-write stays deferred to #5108.
**Independent Test**: The error message names `git -C <repo> worktree add <worktree> <coord_branch>`, not `doctor workspaces --fix`.
**Prompt**: `/tasks/WP07-coord-remedy-text.md`
**Requirement Refs**: FR-010, C-002

### Included Subtasks

T022 Red-first: assert the remedy text currently names `doctor workspaces --fix`.
T023 In `coordination/surface_resolver.py` (`CoordinationWorktreeUnmaterialized.__init__` / `next_step`), compose the concrete `git worktree add` command (mirror the #2240 `_coordination_doctor.py` hint) via `CoordinationWorkspace.worktree_path`/`branch_name`.
T024 [P] Optional defensive `except CoordinationWorktreeUnmaterialized` arm in `cli/commands/decision.py` for a clean CLI message.

### Dependencies

- None.

### Risks & Mitigations

- Strictly remedy text; do NOT touch `CoordinationWorkspace.resolve` (owned by #5108) — C-002.

---

## Dependency & Execution Summary

- **Sequence**: WP03 (foundational) → {WP04, WP05}. WP01, WP02, WP06, WP07 are independent and can proceed in any order.
- **Parallelization**: WP01/WP02/WP06/WP07 in parallel; WP04 and WP05 in parallel after WP03.
- **MVP Scope**: WP01 + WP02 restore a green fresh-env baseline immediately; WP03–WP05 fix the core derived-state defect.

---

## Requirements Coverage Summary

| Requirement ID | Covered By Work Package(s) |
|----------------|----------------------------|
| FR-001 | WP01 |
| FR-002 | WP02 |
| FR-003 | WP04 |
| FR-004 | WP05 |
| FR-005 | WP05 |
| FR-006 | WP05 |
| FR-007 | WP05 |
| FR-008 | WP05 |
| FR-009 | WP06 |
| FR-010 | WP07 |
| NFR-001 | WP05 |
| NFR-002 | WP03 |
| NFR-003 | WP05, WP06 |
| NFR-004 | WP03, WP04, WP05 |
| C-001 | WP01 |
| C-002 | WP07 |
| C-003 | WP03, WP05 |
| C-004 | WP01–WP07 |

---

## Subtask Index (Reference)

| Subtask ID | Summary | Work Package | Priority | Parallel? |
|------------|---------|--------------|----------|-----------|
| T001 | Reproduce charter test failures | WP01 | P1 | No |
| T002 | Add cwd-isolation fixture | WP01 | P1 | No |
| T003 | Verify green + no prod change | WP01 | P1 | No |
| T004 | Mirror pytestarch into dev group | WP02 | P1 | No |
| T005 | Regenerate uv.lock | WP02 | P1 | No |
| T006 | pyproject-shape guard | WP02 | P1 | Yes |
| T007 | Extract shared re-materialize helper | WP03 | P0 | No |
| T008 | Unit-test the helper | WP03 | P0 | Yes |
| T009 | Red-first lane-alloc test | WP04 | P1 | No |
| T010 | Regenerate snapshot in allocation | WP04 | P1 | No |
| T011 | Human-conflict control test | WP04 | P1 | Yes |
| T012 | Red-first squash divergence test | WP05 | P1 | No |
| T013 | Post-squash re-materialize/re-fold hook | WP05 | P1 | No |
| T014 | mission-events union driver (4 surfaces) | WP05 | P1 | No |
| T015 | Enumerate mission-events in artifacts | WP05 | P1 | No |
| T016 | lifecycle.jsonl + decisions/index.json decision | WP05 | P1 | No |
| T017 | Correct C-006 guard classification | WP05 | P1 | No |
| T018 | Driver + guard tests | WP05 | P1 | Yes |
| T019 | Red-first feature_dir disagreement test | WP06 | P2 | No |
| T020 | Primary-anchor planning feature_dir | WP06 | P2 | No |
| T021 | Status-action regression | WP06 | P2 | Yes |
| T022 | Red-first remedy-text test | WP07 | P2 | No |
| T023 | Compose git worktree add remedy | WP07 | P2 | No |
| T024 | Defensive CLI except arm | WP07 | P2 | Yes |
