---
work_package_id: WP01
title: 'Campsite: extract guard and resolver helpers (behaviour-preserving)'
dependencies: []
requirement_refs:
- FR-019
- NFR-005
planning_base_branch: issue-5100-single-branch-topology
merge_target_branch: issue-5100-single-branch-topology
branch_strategy: Planning artifacts for this mission were generated on issue-5100-single-branch-topology. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5100-single-branch-topology unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-single-branch-topology-honesty-01M3M22V
base_commit: b1d397061491858776902e2ea97355cb3d50457d
created_at: '2026-09-28T13:49:59.111645+00:00'
subtasks:
- T001
- T002
- T003
phase: Phase 0 - Campsite
history:
- at: '2026-09-28T14:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/workspace/
create_intent:
- tests/specify_cli/workspace/test_resolver_arms.py
- tests/lanes/test_destroyed_lane_guard_helpers.py
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/workspace/context.py
- tests/specify_cli/workspace/test_resolver_arms.py
- tests/lanes/test_destroyed_lane_guard_helpers.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Campsite: extract guard and resolver helpers (behaviour-preserving)

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field in the event log (`spec-kitty agent tasks status --mission single-branch-topology-honesty-01M3M22V`). If feedback exists, address every item before you finish.

---

## Objectives & Success Criteria

This is a **tidy-first, behaviour-preserving** step. It follows charter Standing Order #2, campsite cleaning. Its purpose is to make the two surfaces that every later WP changes small and individually testable:

1. **The destroyed-lane guard helpers** in `src/specify_cli/lanes/worktree_allocator.py`:
   - `_canonical_wp_lane_value`
   - `_lane_base_reachable_from_target`
   - `_refuse_if_lane_destroyed` (lines ~239–353)

   Keep them in `worktree_allocator.py`, but restructure `_refuse_if_lane_destroyed` into two parts:
   - a pure *decision* function: it takes the context, the WP lane state and a reachability flag, and returns an enum/literal verdict;
   - a thin *effect* wrapper that raises.

   WP07 later swaps the reachability input for a tip-based one without touching the decision table's shape.

2. **`_resolve_workspace_for_wp_impl`** in `src/specify_cli/workspace/context.py` (~747–868). Split it into one private helper per arm:
   - `_resolve_planning_artifact_arm`
   - `_resolve_context_arm`
   - `_resolve_planning_lane_arm`
   - `_resolve_code_lane_arm`

   The top-level function should read as a short dispatch. Every function must stay at cyclomatic complexity ≤ 15.

**Done when**:
- no public behaviour changes;
- every existing test named below passes unchanged;
- new focused tests cover each extracted helper directly;
- `ruff check`, `ruff format --check` and `mypy --strict` are clean on the touched files.

## Context & Constraints

- Read first: `.kittify/charter/charter.md`, `kitty-specs/single-branch-topology-honesty-01M3M22V/plan.md` (especially the "Post-plan squad folds" section), `research.md` R-1 and R-6/R-7, and `data-model.md`.
- **No behaviour change.** A test that changes its expectation in this WP is a defect in this WP.
- `worktree_allocator.py` is *owned by WP07*. This WP makes a narrowly scoped out-of-map edit there: extracting the guard helpers only. Record that rationale in the Activity Log. Do not edit other parts of the allocator.
- Keep the existing `DestroyedLaneError` class, its `error_code`, and every message byte-identical.
- The #4889 landing-pass fail-closed semantics must be preserved exactly: an unreadable status surface with a persisted context raises. See the docstring at `worktree_allocator.py:300-333`.

## Branch Strategy

- **Strategy**: lanes (populated by finalize-tasks)
- **Planning base branch**: issue-5100-single-branch-topology
- **Merge target branch**: issue-5100-single-branch-topology

Execution worktrees are allocated per computed lane from `lanes.json`. Run `spec-kitty implement WP01 --mission single-branch-topology-honesty-01M3M22V` and work in the resolved workspace.

## Subtasks & Detailed Guidance

**Red-first exemption (charter C-011; analysis finding C2).** This WP preserves behaviour: it pins current behaviour rather than adding new behaviour. Its proof is:

- every existing test named in the Test Strategy passes unchanged;
- the new helper tests pass on the refactored code and assert today's semantics.

State this in the Activity Log.


### Subtask T001 – Extract destroyed-lane guard helpers

- **Purpose**: WP07 needs a pure decision function it can test in isolation, and whose inputs it can change (from a base-reachability flag to a tip verdict).
- **Steps**:
  1. Read `worktree_allocator.py:230-360` and the call site of `_refuse_if_lane_destroyed` (around `:853`).
  2. Introduce a small `Literal`/`Enum`, e.g. `_GuardVerdict = Literal["proceed", "refuse_destroyed", "refuse_unreadable"]`.
  3. Add a pure function `_destroyed_lane_verdict(*, has_context: bool, wp_state: str | None, status_unreadable: bool, base_reachable: bool) -> _GuardVerdict` that encodes today's table exactly:
     - no context → `proceed`;
     - status unreadable with context → `refuse_unreadable`;
     - state not in `_DESTROYED_LANE_TRIGGER_STATES` → `proceed`;
     - base reachable → `proceed`;
     - otherwise `refuse_destroyed`.
  4. Reduce `_refuse_if_lane_destroyed` to: gather the inputs (keep the existing lazy imports), call the verdict function, and raise `DestroyedLaneError` for either refuse verdict, exactly as today.
- **Files**: `src/specify_cli/lanes/worktree_allocator.py` (out-of-map, rationale logged).
- **Notes**: keep the `from None` exception chaining as it is. Do not rename the public error.

### Subtask T002 – Split `_resolve_workspace_for_wp_impl` into per-arm helpers

- **Purpose**: WP02, WP04 and WP05 each add or reorder an arm. Separate helpers keep complexity down and make arm precedence explicit.
- **Steps**:
  1. Move each early-return block into its own private function that returns `ResolvedWorkspace | None`. Each helper takes `(repo_root, mission_slug, wp_id, normalized_wp, execution_mode)` or whatever subset it needs.
  2. The top-level function becomes a sequence of arm calls in today's precedence order: planning_artifact kind → persisted context → lanes.json planning lane → code lane. It keeps the `ValueError` for an unassigned WP.
  3. Keep the existing comments that explain the placement-seam calls, moved into the helpers.
  4. Do **not** add the `effective_root` parameter or any topology read yet. Those arrive in WP04.
- **Files**: `src/specify_cli/workspace/context.py`.

### Subtask T003 – Focused tests for the extracted helpers

- **Purpose**: Sonar new-code coverage. Also, later WPs extend these tests instead of relying on broad integration runs.
- **Steps**:
  1. Create `tests/lanes/test_destroyed_lane_guard_helpers.py`. Parametrize over every row of the verdict table (at least 6 cases, including each trigger state and a terminal state).
  2. Create `tests/specify_cli/workspace/test_resolver_arms.py`. For each arm helper, build the minimal fixture: a tmp repo with a `kitty-specs/<slug>/tasks/WP01-x.md` carrying `execution_mode` frontmatter, plus a `lanes.json` where the arm needs one. Reuse helpers from `tests/runtime/test_workspace_context_unit.py` where possible. Assert the returned `ResolvedWorkspace` fields (`resolution_kind`, `worktree_path`, `branch_name`, `lane_id`).
  3. Mark the new tests `fast` or `unit`, per the markers in `pytest.ini`.
- **Files**: the two new test files.

## Test Strategy

Run these targeted tests (C-007):

```bash
.venv/bin/python -m pytest tests/lanes/test_destroyed_lane_guard_helpers.py tests/specify_cli/workspace/test_resolver_arms.py -q
.venv/bin/python -m pytest tests/lanes/test_issue_4889_destroyed_lane_guard.py tests/lanes/test_lane_allocation_integrity_e2e.py tests/lanes/test_worktree_allocator.py tests/specify_cli/lanes/test_worktree_allocator_recovery.py tests/specify_cli/lanes/test_worktree_allocator_coord.py -q
.venv/bin/python -m pytest tests/runtime/test_workspace_context_unit.py tests/specify_cli/test_workspace_context_tombstone.py tests/orchestrator_api/test_issue_4889_caller_independence.py -q
.venv/bin/ruff check src/specify_cli/lanes/worktree_allocator.py src/specify_cli/workspace/context.py && .venv/bin/ruff format --check src/specify_cli/lanes/worktree_allocator.py src/specify_cli/workspace/context.py
.venv/bin/mypy --strict src/specify_cli/lanes/worktree_allocator.py src/specify_cli/workspace/context.py
```

Record the commands and pass/fail counts in the Activity Log.

## Risks & Mitigations

- **Accidental behaviour change in the precedence order.** Mitigation: the resolver-arm tests pin each arm, and the existing workspace tests must pass unmodified.
- **Import cycles from moving lazy imports.** Keep the lazy imports inside the helper bodies exactly where they were.

## Review Guidance

- Diff-read for behaviour identity: same exceptions, same messages, same precedence.
- Confirm there is no topology read and no new parameter.
- Confirm the complexity of every touched function is ≤ 15 (`ruff check --select C901`).

## Activity Log

- 2026-09-28T14:00:00Z – system – Prompt created.
