---
work_package_id: WP01
title: Deterministic dry-run preview input for the golden
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
planning_base_branch: main
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on main. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
phase: Phase 1 - Fix
history:
- at: '2026-11-02T16:56:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/upgrade/test_upgrade_outcome_rendering.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/upgrade/test_upgrade_outcome_rendering.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '#7030'
---

# Work Package Prompt: WP01 – Deterministic dry-run preview input for the golden

## ⚡ Do This First: Load Agent Profile

Use the `/spk-charter-profile-load` skill to load the agent profile specified in the frontmatter, and behave according to its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: pi

---

## ⚠️ IMPORTANT: Review Feedback

Check `review_ref` in the event log (`spec-kitty agent tasks status --mission golden-dry-run-order-independence-01M6EJX3`) and address every item before handing back.

## Objectives & Success Criteria

- `test_golden_applied_dry_run` passes when selected alone (`-k golden_applied_dry_run`) and when
  the whole module runs, from a fresh process, with no change to the pinned expected text (FR-001,
  FR-002, NFR-001, SC-001, SC-002).
- The golden still proves the dry run prints the supporting-repair preview: if the command stops
  consulting the preview, the golden fails (FR-003).
- `git diff --stat origin/main -- src/` stays empty (FR-004, SC-003).
- No assertion is weakened: `_GOLDEN_APPLIED_DRY_RUN` remains an exact-match constant, no skip,
  xfail, deselect or marker is added (C-001).

## Context & Constraints

- The failure (issue #7030): the golden's preview line came from the live
  `upgrade_module._supporting_repair_preview(project_path)`, which assesses the pytest-isolated
  home. `tests/conftest.py::_isolated_worker_home` is keyed per xdist worker, not per test, so an
  empty home yields `Would repair 125 ...` while a home materialized by an earlier test yields
  `Would repair 1 ...`. `test_golden_applied_run` materializes it, which is why the module run passes.
- The seam already exists and is already used in this module: `_stub_incomplete_preview`
  (line ~343) for matrix rows, `test_step_dry_run_with_a_complete_preview_prints_the_notice_and_reports_nothing`
  (line ~655), and `tests/upgrade/test_upgrade_integration.py` (line ~552). No `src/` hook needed
  (C-002).
- No test in `tests/` exercises the live preview count today — every call site stubs it — so
  stubbing in the golden removes nothing that was covered.
- Do not change `tests/conftest.py`, `_stub_incomplete_preview`, the matrix rows, or
  `tests/upgrade/test_upgrade_integration.py` (C-003, NFR-002).
- The dry-run path prints a *complete* preview in text mode (`_dry_run_surface_report`); keep the
  golden on that branch (`incomplete=False`).
- Repository rules: `uv run --frozen pytest ...`, ruff clean, `NO_FULL_HEAVY_SUITES_IN_MISSION` (run
  the owning module plus the neighbouring upgrade suites only, never the full suite).

## Branch Strategy

- **Strategy**: single_branch (set by finalize-tasks)
- **Planning base branch**: kitty/mission-golden-dry-run-order-independence-01M6EJX3
- **Merge target branch**: kitty/mission-golden-dry-run-order-independence-01M6EJX3

Implementation command: `spec-kitty agent action implement WP01 --agent python-pedro --mission golden-dry-run-order-independence-01M6EJX3`

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first reproduction

- **Purpose**: witness the defect through the pre-existing entry point before changing anything
  (DIRECTIVE_034; ATDD-first).
- **Steps**:
  1. On the branch, run the node-selected form from a clean process:
     `uv run --frozen pytest tests/upgrade/test_upgrade_outcome_rendering.py -k golden_applied_dry_run -q`
     and capture the assertion diff (`- Would repair 1 ...` / `+ Would repair 125 ...`).
  2. Confirm the whole-module run is green:
     `uv run --frozen pytest tests/upgrade/test_upgrade_outcome_rendering.py -q`.
  3. Append both results to the mission tracer
     (`spec-kitty agent tracer-append --mission golden-dry-run-order-independence-01M6EJX3 --category approach --entry "..."`).
- **Validation**: step 1 fails with the count mismatch, step 2 passes. If step 1 already passes,
  stop and report: the environment differs from the issue's and the fix's premise is gone.

### Subtask T002 – Stub the preview from one constant

- **Purpose**: make the golden's preview input fixed text, not the isolated home's state.
- **Steps**:
  1. Beside `_PREVIEW_NOTICE`, add a constant holding the complete-preview sentence the pinned
     golden already contains, e.g.
     `_GOLDEN_DRY_RUN_PREVIEW = "Would repair 1 supporting surface paths (including 0 manifests). Use --plan-json for full repair details."`
     with a one-line comment saying the count is environment-derived, which is why the golden fixes
     it here (issue #7030).
  2. In `test_golden_applied_dry_run`, replace the live call with a recording stub over
     `upgrade_module._supporting_repair_preview` returning
     `(_GOLDEN_DRY_RUN_PREVIEW, False)` — the *complete* preview branch.
  3. Keep `_GOLDEN_APPLIED_DRY_RUN` byte-identical; the wrapped two-line rendering it pins must
     still match (the console width fixture is `_GOLDEN_WIDTH = 80`).
- **Validation**: the pinned text is unchanged in the diff (`git diff` touches only the constant and
  the test body).

### Subtask T003 – Prove the preview line is still covered

- **Purpose**: a stub the run never consults would silently drop the assertion
  (acceptance-criteria-non-vacuity: no-vacuous-oracle).
- **Steps**:
  1. Capture the stub's calls (a small list appended in the stub body, or a `MagicMock` whose
     `call_count`/`call_args_list` you assert).
  2. Assert it was consulted exactly once in the golden, with the project path the command was
     invoked on.
- **Validation**: comment out the production call to `_supporting_repair_preview` in
  `_dry_run_surface_report` locally and confirm the golden fails (then revert — do not commit any
  `src/` change).

### Subtask T004 – Verification

- **Purpose**: demonstrate both selections agree and nothing neighbouring broke.
- **Steps**:
  1. `uv run --frozen pytest tests/upgrade/test_upgrade_outcome_rendering.py -k golden_applied_dry_run -q`
     (twice in a row), then the whole module.
  2. `uv run --frozen pytest tests/upgrade/test_upgrade_integration.py tests/upgrade/test_upgrade_cli_contract.py -q`
     (the neighbouring upgrade surfaces that share the preview stub and the command).
  3. `uv run --frozen ruff check tests/upgrade/test_upgrade_outcome_rendering.py` and
     `uv run --frozen ruff format --check tests/upgrade/test_upgrade_outcome_rendering.py`.
  4. `git diff --stat origin/main -- src/` is empty.
- **Validation**: every command green; record commands and counts in the WP notes and the PR
  `## Tests run` section.

## Review Guidance

- Verify the expected-output constant was not edited (diff must not touch `_GOLDEN_APPLIED_DRY_RUN`
  or `_GOLDEN_APPLIED`).
- Verify the stub exercises the complete-preview branch, not the incomplete one, and that the
  goldens' pinned line is the rendering of the constant.
- Verify the call-count assertion would fail if the preview stopped being consulted.
- Verify no skip/xfail/marker, no `src/` change, no conftest change.
- Verify the evidence: both the node-selected and the whole-module run are reported with counts.

## Activity Log

- 2026-11-02T16:56:00Z – system – Prompt generated via /spec-kitty.tasks
