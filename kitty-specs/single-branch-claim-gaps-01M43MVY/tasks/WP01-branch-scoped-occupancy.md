---
work_package_id: WP01
title: Branch-scoped single_branch occupancy with a runnable remedy
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- NFR-001
- NFR-002
- C-001
- C-002
- C-003
- C-004
- C-005
planning_base_branch: issue-5680-single-branch-claim-gaps
merge_target_branch: issue-5680-single-branch-claim-gaps
branch_strategy: Planning artifacts for this mission were generated on issue-5680-single-branch-claim-gaps. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5680-single-branch-claim-gaps unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-single-branch-claim-gaps-01M43MVY
base_commit: af4b955d7d69311b554721bf0b0e0bcdd7958697
created_at: '2026-10-04T14:31:27.703903+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Fix
history:
- at: '2026-10-04T15:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/lanes/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/lanes/checkout_occupancy.py
- src/specify_cli/lanes/implement_support.py
- tests/lanes/test_checkout_occupancy.py
- tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py
- tests/integration/test_single_branch_write_checkout_e2e.py
- docs/changelog/CHANGELOG.md
- docs/context/topology.md
- CLAUDE.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Branch-scoped single_branch occupancy with a runnable remedy

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

If no profile is specified, run `spec-kitty agent profile list` and select the best match for this work package's `task_type` and `authoritative_surface`.

---

## Objective

Stop an `in_progress` work package of a single_branch mission from blocking claims when that mission's write branch is not the branch the write checkout is on (#5680). Keep the refusal for a live occupant on the same write branch, and give that refusal a runnable remedy. Close #5663 with its existing pin. Both claim verbs (`spec-kitty implement`, `spec-kitty agent action implement`) must behave identically.

Implementation command: `spec-kitty agent action implement WP01 --agent claude --mission single-branch-claim-gaps-01M43MVY`

## Context

- Read first: [`research/code-grounding.md`](../research/code-grounding.md) and [`plan.md`](../plan.md), the "Decision" section in particular.
- The scan is `src/specify_cli/lanes/checkout_occupancy.py::in_progress_wps_in_write_checkout`. Its only caller is `src/specify_cli/lanes/implement_support.py::_ensure_repo_root_checkout_available`, which raises `WriteCheckoutOccupiedError`.
- The predicate is defined in plan.md. An occupant counts only when `not is_mission_completed(feature_dir)` AND `single_branch_write_ref(stored_topology, meta["mission_branch"], meta["target_branch"]) == current branch of the write checkout`. If either value is unknown, the occupant counts (fail closed).
- Doctrine: Charter Standing Order 4, procedures `test-first-bug-fixing` and `disciplined-defect-diagnosis`, ADR 2026-07-17-1 (red-first; `@pytest.mark.regression` only while transitional).
- Non-goals:
  - Do not weaken the guard for live same-branch missions.
  - Never edit `kitty-specs/reconcile-flake-family-01M34HR7/`.
  - Add no new gates.

## Branch Strategy

- **Strategy**: populated by finalize-tasks
- **Planning base branch**: issue-5680-single-branch-claim-gaps
- **Merge target branch**: issue-5680-single-branch-claim-gaps

### Subtask T001: Tidy-first: extract the per-mission candidate check

- **Purpose**: make room for one more filter without pushing `in_progress_wps_in_write_checkout` towards the complexity ceiling (Charter SO-2).
- **Steps**:
  1. Move the per-mission filtering (topology read, repo-root WP ids, completion check) into a private helper, `_occupancy_candidate_wp_ids(feature_dir) -> frozenset[str]`, that returns an empty set for a non-candidate.
  2. Keep the behaviour byte-identical.
  3. Commit it alone as `refactor(lanes): …`.
- **Files**: `src/specify_cli/lanes/checkout_occupancy.py`
- **Validation**: `tests/lanes/test_checkout_occupancy.py` and `tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py` stay green and unchanged.

### Subtask T002: Red-first reproductions through both claim verbs

- **Purpose**: show #5680 is red through its real entry points before the fix (C-005).
- **Steps**:
  1. In `tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py`, add a `@pytest.mark.regression` test (issue #5680 in its docstring):
     - Occupant mission A has `target_branch: trunk` and WP01 `in_progress`, committed on `trunk`.
     - The operator checks out `next-topic` from that tip. Claimant mission B has `target_branch: next-topic`.
     - `spec-kitty implement WP01 --mission B` must succeed.
  2. In `tests/integration/test_single_branch_write_checkout_e2e.py`, add the same scenario through `spec-kitty agent action implement` (`agent_loop_mission`-style fixture), marked `regression`.
  3. Run both and record them RED, with `WRITE_CHECKOUT_OCCUPIED` naming mission A. Commit them as `test(lanes): …` before the fix.
- **Validation**: both tests fail on the pre-fix code and point at the occupancy refusal.

### Subtask T003: Branch-scope the predicate

- **Purpose**: FR-001/FR-002/FR-003 and NFR-001.
- **Steps**:
  1. Resolve the write checkout's current branch once per scan (`specify_cli.core.git_ops.get_current_branch`).
  2. For each candidate mission, read its `meta.json` with the canonical fail-closed reader, compute `single_branch_write_ref(topology, meta.get("mission_branch"), meta.get("target_branch"))`, and skip the mission when the write branch is known and differs from the current branch. The existing `read_topology` call does not return meta, so either read meta once and derive the topology from the same dict, or add one cheap meta read. Either way, no git subprocess per mission.
  3. Fail closed when the current branch is `None` or `target_branch` is absent.
  4. Update the docstring: add the new filter step and its authority.
  5. Unit tests in `tests/lanes/test_checkout_occupancy.py`:
     - occupant on another write branch is not reported;
     - occupant on the same write branch is reported (control);
     - a protected-target mint (`mission_branch`) is honoured;
     - missing `target_branch` fails closed;
     - detached HEAD fails closed.
- **Validation**: the T002 repros turn green, and every existing test stays green.

### Subtask T004: Runnable remedy in the occupied refusal

- **Purpose**: FR-005.
- **Steps**:
  1. In `_ensure_repo_root_checkout_available`, the message keeps `Move <WP> out of in_progress` and adds:
     - the occupant's write branch (equal to `expected_branch` after T003);
     - the command `spec-kitty agent tasks move-task <WP> --to blocked --mission <occupant> --note "<reason>"`.
  2. Update the isolated refusal test to assert both.
  3. Add a CLI-level test that runs the suggested `move-task` and retries the claim, which then succeeds.
- **Validation**: the refusal tests pass, and the suggested command really clears the occupant.

### Subtask T005: Retire the transitional markers, then docs and changelog

- **Purpose**: C-005, FR-006, FR-007.
- **Steps**:
  1. Drop `@pytest.mark.regression` from the T002 repros and keep them in their functional suites with descriptive names.
  2. Add paired controls to the same files:
     - (a) a stale finished-mission WP no longer blocks;
     - (b) a live other-mission `in_progress` WP still refuses `WRITE_CHECKOUT_OCCUPIED`;
     - (c) resuming the same WP is still allowed.
  3. Add a `docs/changelog/CHANGELOG.md` `[Unreleased]` entry: bold, impact-first, `(#5680)`, then before → after.
  4. Update the `WRITE_CHECKOUT_OCCUPIED` wording in `CLAUDE.md` "Execution Workspace Strategy" and in `docs/context/topology.md`.
  5. #5663: no code. Cite `test_action_implement_records_claim_base_and_reaches_review` in the PR.
- **Validation**:
  - `uv run --frozen python -m scripts.docs.check_changelog_style`;
  - `pytest tests/architectural/test_no_legacy_terminology.py tests/architectural/test_issue_named_test_census.py tests/architectural/test_no_dead_symbols.py tests/architectural/test_layer_rules.py tests/architectural/test_module_length_agreement.py`.

## Definition of Done

- T001-T005 are recorded done via `spec-kitty agent tasks mark-status`.
- The T002 repros were red before T003, and that is recorded in the WP activity or the tracer.
- These pass:
  - `make test-fast`;
  - `tests/lanes/`;
  - `tests/integration/test_single_branch_write_checkout_e2e.py`;
  - `tests/specify_cli/cli/commands/test_single_branch_implement_refusals.py`;
  - the named architectural gate files.
- `ruff check`, `ruff format --check --force-exclude` and `mypy` on the changed sources are clean, with complexity at 15 or below.
- No test in the diff still carries `@pytest.mark.regression`.

## Risks

- **A vacuous repro:** the claimant fixture must sit on a different write branch from the occupant, and the control must share a branch. Assert the branch names in the test.
- **Meta-read cost:** at most one extra JSON read per single_branch mission, and no git calls.
- **Message phrase drift:** existing tests assert `Move WP01 out of in_progress`, so keep it.

## Reviewer Guidance

- Verify red→green: check out the T002 commit and run the two repros (red), then the head (green).
- Confirm C-001 with the live-occupant control on the same fixture shape.
- Confirm the write branch comes only from `single_branch_write_ref` (C-003).
- Confirm no edit under `kitty-specs/reconcile-flake-family-01M34HR7/` (C-002).

## Activity Log
