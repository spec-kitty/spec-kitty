---
work_package_id: WP01
title: Provision the move-task fixture's charter and pin it red-first
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- NFR-001
- NFR-002
- C-001
- C-002
- C-003
- SC-001
- SC-002
- SC-003
planning_base_branch: issue-7073-move-task-fixture-charter-provisioning
merge_target_branch: issue-7073-move-task-fixture-charter-provisioning
branch_strategy: Planning artifacts for this mission were generated on issue-7073-move-task-fixture-charter-provisioning. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7073-move-task-fixture-charter-provisioning unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-move-task-fixture-charter-provisioning-01M6GA71
base_commit: 1648c0f22057bfdf5e35a61800dcb0ae4fedbcc4
created_at: '2026-11-03T09:03:59.325714+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 1 - Fixture fidelity
history: []
agent_profile: python-pedro
authoritative_surface: tests/tasks/
create_intent:
- docs/changelog/unreleased/
execution_mode: code_change
model: ''
owned_files:
- tests/tasks/test_move_task_git_validation_unit.py
- docs/changelog/unreleased/
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Provision the move-task fixture's charter and pin it red-first

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load `python-pedro` (implementer) and behave according to its
guidance before parsing the rest of this prompt.

## ⚠️ IMPORTANT: Review Feedback

Check the `review_ref` field via `spec-kitty agent tasks status`; address every item before completing the work.

## Objectives & Success Criteria

- `tests/tasks/test_move_task_git_validation_unit.py::git_repo_with_worktree` builds a **provisioned** project:
  `.kittify/charter/activation.yaml` carries the activated mission types `spec-kitty init` would write.
- `resolve_mission_type_context(repo_root, mission_type="software-dev")` returns the real curated profile
  (non-empty `action_sequence`) instead of raising `UnknownMissionTypeError`.
- `charter.activation.api.code_producing_for(repo_root, "software-dev")` emits **no**
  `charter.activation.mission_type_profiles` WARNING record (no `exc_info` fallback traceback).
- Two new regression tests fail on the base commit and pass on the branch; the 15 pre-existing node ids,
  decorators, assertions and fail/pass set are unchanged; `git diff origin/main..HEAD -- src/` is empty.

## Context & Constraints

- Issue #7073. Grounding and measurements: `kitty-specs/move-task-fixture-charter-provisioning-01M6GA71/research.md`.
- The repository already has the blessed provisioning wrapper: `tests/_factories/__init__.py::provision_test_charter`
  — a thin wrapper over the production provisioner, explicitly "NOT a second, test-only seeder". Use it; do not
  hand-write `mission_type_activations`.
- PR #7100 (issue #7057, still open) edits the same fixture helper. Keep your hunks textually disjoint: #7100
  owns the WP01 `owned_files` frontmatter, the lane worktree's `Add implementation` commit and one node's
  `--agent`; you own the `.kittify/config.yaml` write region and a new test class.
- No `src/` change. No assertion loosened. No skip, xfail, deselection, marker or `--force`.

## Branch Strategy

- **Strategy**: lane worktree from the mission branch
- **Planning base branch**: `main`
- **Merge target branch**: `main`

> These fields are populated by `spec-kitty agent mission finalize-tasks`. Do not change them by hand.

## Subtasks & Detailed Guidance

### T001 – Record the base red

- **Purpose**: the recorded pre-fix evidence the PR quotes.
- **Steps**: on the planning base commit, run
  `uv run --frozen pytest -q -p no:randomly -n0 tests/tasks/test_move_task_git_validation_unit.py` and capture
  (a) the 8 `IMPLEMENTATION_MISSING` failures that #7057 owns and (b) the
  `charter.activation.mission_type_profiles.UnknownMissionTypeError: Unknown mission type 'software-dev'. No
  registered mission types are available.` traceback emitted by the swallowed-exception fallback.
- **Files**: none (recorded evidence).
- **Parallel?**: no.

### T002 – Add the red-first regression pair

- **Purpose**: pin the subject (an unprovisioned fixture), not the assertion.
- **Steps**: append a `TestFixtureCharterProvisioning` class to
  `tests/tasks/test_move_task_git_validation_unit.py` with two tests:
  1. `resolve_mission_type_context(repo_root, mission_type="software-dev")` returns `mission_type ==
     "software-dev"` and a non-empty `action_sequence` (a neutral/fallback bundle is empty, so this is the
     positive control);
  2. `code_producing_for(repo_root, "software-dev")` returns `True` **and** no
     `charter.activation.mission_type_profiles` record is logged at WARNING (`caplog`).

  Run them on the base commit and record the red output (test 1: `UnknownMissionTypeError`; test 2: the
  "using the built-in default" record present).
- **Files**: `tests/tasks/test_move_task_git_validation_unit.py`.
- **Parallel?**: yes, with T005/T006.

### T003 – Provision the fixture

- **Purpose**: make the fixture a project `spec-kitty init` would have produced.
- **Steps**: in `git_repo_with_worktree`, immediately after `.kittify/config.yaml` is written and **before**
  `git add .` / `Initial commit`, call `provision_test_charter(repo)` (imported from `tests._factories`), with a
  short comment saying why (the guard under test reads a capability through the mission-type resolver, so an
  unprovisioned fixture degrades it to a swallowed-fallback value). Provisioning before the first commit keeps
  the fixture's commit count and the `Add implementation` head subject that other nodes assert.
- **Files**: `tests/tasks/test_move_task_git_validation_unit.py`.
- **Parallel?**: no.

### T004 – Prove non-vacuity and behaviour parity

- **Purpose**: prove the pin can fail and the fix changes nothing else.
- **Steps**: re-run the module (15 nodes, same ids via `--collect-only`); then comment out / revert the
  provisioning call and show both new tests fail again, and restore it. Confirm the pre-existing nodes'
  fail/pass set is identical to T001's on the same base (with PR #7100's fixture re-pin applied locally the whole
  module is 15/15; without it the same 8 nodes fail with the same `IMPLEMENTATION_MISSING` message).
- **Files**: none (evidence).
- **Parallel?**: no.

### T005 – Lint, format and type gates

- **Purpose**: the module must pass the gates CI would run on it.
- **Steps**: `uv run --frozen ruff check`, `ruff format --check --force-exclude`, and `mypy` on the edited
  module, on the branch and on the base; record identical-or-better (mypy has 16 pre-existing `no-untyped-def`
  errors in this module — do not introduce new ones, and do not mass-annotate the module).
- **Files**: none.
- **Parallel?**: yes.

### T006 – Changelog fragment

- **Purpose**: the repo assembles the changelog from per-PR fragments (#6988).
- **Steps**: add `docs/changelog/unreleased/<pr>.internal.md` (internal: test-only) with one entry naming #7073
  and the fixture-provisioning change; run `python -m scripts.docs.check_changelog_style` and
  `python -m scripts.docs.check_spelling --pass unreleased`.
- **Files**: `docs/changelog/unreleased/<pr>.internal.md`.
- **Parallel?**: yes.

## Test Strategy

- `uv run --frozen pytest -q -p no:randomly -n0 tests/tasks/test_move_task_git_validation_unit.py` — the module
  under change (out-of-matrix directory; local run is the evidence).
- Regression neighbours: `tests/specify_cli/cli/commands/charter/` (activation/provisioning consumers) and
  `tests/agent/test_review_validation_unit.py` (shares `write_single_lane_manifest`).
- Type check: `uv run --frozen mypy tests/tasks/test_move_task_git_validation_unit.py` (0 new diagnostics).

## Risks & Mitigations

- **Vacuous pin** — `code_producing_for` is `True` before and after; assert the resolved bundle and the absence
  of the fallback record.
- **Commit-shape drift** — provision before the fixture's first commit.
- **Collision with #7100** — disjoint hunks only; rebase only on a genuine `CONFLICTING` mergeability report.

## Review Guidance

- Confirm the diff is test-side only (`git diff origin/main..HEAD -- src/` empty) and that the new tests are the
  only added nodes (15 → 17 collected).
- Confirm the pin fails when the provisioning call is removed (revert proof), i.e. it is not no-op passable.
- Confirm no skip/xfail/deselect/marker/`--force` was added and no existing assertion was edited.

## Progress & Status

- `spec-kitty agent tasks add-history WP01 --note "<what you did>"`
- `spec-kitty agent tasks move-task WP01 --to <status>`
- `spec-kitty agent tasks status`
