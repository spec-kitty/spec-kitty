---
work_package_id: WP01
title: Fail-closed accept gate on absent lanes.json
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- NFR-001
- NFR-002
- NFR-003
planning_base_branch: issue-4891-accept-fail-closed-missing-lanes
merge_target_branch: main
branch_strategy: Planning artifacts for this mission were generated on issue-4891-accept-fail-closed-missing-lanes. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into main unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-accept-fail-closed-missing-lanes-01M3CC1V
base_commit: d5cbc114304b0e247b46a7641d209728cea98470
created_at: '2026-09-25T13:37:20.383261+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Fail-closed guard
history:
- at: '2026-09-25T13:30:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/acceptance/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5
owned_files:
- src/specify_cli/acceptance/gates_core.py
- tests/characterization/test_trio_pure_cores.py
- tests/cross_cutting/misc/test_acceptance_support.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Fail-closed accept gate on absent lanes.json

## ⚡ Do This First: Load Agent Profile

Load the `python-pedro` profile (implementer role) via the resolver-backed profile-load skill and
behave per its guidance before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Objectives & Success Criteria

Fix P0 **#4891**: `spec-kitty accept` silently skips the entire acceptance-matrix gate when
`kitty-specs/<slug>/lanes.json` is absent — exit 0, `summary.ok=True`, acceptance recorded and
committed on an all-`pending` matrix. Make absence **fail closed**.

Done when:

- **FR-001**: with `lanes.json` absent and any criterion unresolved (or the matrix missing),
  `spec-kitty accept` exits non-zero and `AcceptanceSummary.ok` is `False`.
- **FR-002**: the absent case records a `blocked_checks` `lanes_manifest` diagnostic **and**
  `skipped_checks` for every acceptance-matrix gate that did not run (presence, evidence,
  negative-invariants, verdict).
- **FR-003**: no `accepted_at` / `accept_commit` / `acceptance_history` is written or committed in
  the absent case.
- **FR-004**: the diagnostic names the recovery (finalize-tasks / `doctor mission-state --fix`),
  matching `MissingLanesError` wording.
- **FR-005**: present-lanes and corrupt-lanes behaviours are unchanged.
- **NFR-002/003**: `ruff check`, `ruff format --check`, `mypy --strict` clean; touched functions ≤15
  complexity; no new suppressions.

## Context & Constraints

- Charter: `.kittify/charter/charter.md` (ATDD-first C-011; single canonical authority; fail-closed).
- Spec / plan / design decisions: `../spec.md`, `../plan.md`, `../tracer-design-decisions.md`.
- **Root cause (verified, current main)**:
  - `src/specify_cli/acceptance/gates_core.py:595-597` `_check_lane_gates` returns early when
    `_resolve_lanes_manifest_or_stop` yields `None`, skipping the branch gate AND the matrix gates.
  - `_resolve_lanes_manifest_or_stop` (`gates_core.py:164-191`) records diagnostics only in the
    `except CorruptLanesError` arm; `read_lanes_json` returning `None` (absent file,
    `lanes/persistence.py:81-104`) returns `None` with nothing recorded.
  - `AcceptanceSummary.ok` (`acceptance/__init__.py:437-448`) consults `activity_issues` but
    **NOT** `skipped_checks` / `blocked_checks`. **→ the fix MUST append an `activity_issue`** to
    flip `ok`; skipped/blocked alone are insufficient.
- **Canonical authority — do NOT make the read coord-aware.** `lanes.json` (`LANE_STATE`) is a
  PRIMARY-partition artifact (`src/mission_runtime/artifacts.py:158-186`). An absent-on-primary
  manifest is genuinely absent for every topology. (See `tracer-design-decisions.md` DD-2.)
- **Scope**: `accept` only. Do not touch `merge`'s `--skip-lanes` opt-in.

## Subtasks & Detailed Guidance

### Subtask T001 – Red-first: invert the codified-bug characterization test

- **Purpose**: ATDD red anchor. `tests/characterization/test_trio_pure_cores.py::test_missing_lanes_manifest_is_a_silent_noop`
  currently asserts `activity_issues == [] and skipped == [] and blocked == []` for absent
  lanes — it **codifies the bug**. Invert it (rename to
  `test_missing_lanes_manifest_blocks_and_skips_all_checks`) to assert the fail-closed shape,
  templated on the sibling `test_corrupt_lanes_json_blocks_and_skips_all_checks`.
- **Files**: `tests/characterization/test_trio_pure_cores.py`.
- **Notes**: keep the `lanes_manifest` blocked-check name — `_recommended_fix_order` already maps
  it to the restore hint (`test_missing_lanes_manifest_blocked_check_recommends_restore`, ~:159-165).
- Confirm RED before the fix.

### Subtask T002 – Red-first: issue-pinned regression case

- **Purpose**: a `@pytest.mark.regression` test pinned to #4891 that drives the real path and
  asserts `summary.ok is False` + recorded blocked/skipped checks when `lanes.json` is absent.
- **Files**: prefer `tests/cross_cutting/misc/test_acceptance_support.py` (drives real
  `collect_feature_summary` / `strict_metadata`). Pin with `@pytest.mark.regression` and a
  `# regression: #4891` comment.
- Confirm RED before the fix.

### Subtask T003 – Fix: fail-closed on genuine absence

- **Purpose**: mirror the `CorruptLanesError` arm for the `None` (absent) case in
  `_resolve_lanes_manifest_or_stop`.
- **Steps**: when `read_lanes_json(feature_dir)` returns `None`, append an `activity_issues`
  message (load-bearing — flips `ok`), a `blocked_checks` `AcceptanceCheckDiagnostic(check="lanes_manifest", ...)`,
  and call `_append_skipped_lane_checks(skipped_checks, reason=..., include_matrix_presence=True)`;
  then return `None`. Source the remediation wording from `MissingLanesError` (finalize-tasks /
  `doctor mission-state --fix`) so operator guidance is single-sourced. Update the misleading
  docstring that calls absence "a silent no-op … flat/legacy mission".
- **Files**: `src/specify_cli/acceptance/gates_core.py`.
- **Notes**: keep the change within `_resolve_lanes_manifest_or_stop`; do not fork
  `_check_lane_gates`. Keep complexity ≤15.

### Subtask T004 – Green + regression watch

- **Purpose**: confirm T001/T002 pass; confirm present-lanes and corrupt-lanes cases unchanged.
- **Files**: run the owned test files + the coord golden paths
  (`tests/integration/test_accept_matrix_coord_partition.py`,
  `tests/integration/test_placement_partition_golden_path.py`) — these must stay green.

### Subtask T005 – e2e summary.ok assertion

- **Purpose**: end-to-end guard that `summary.ok is False` (and no acceptance recorded) when
  `lanes.json` is absent, at the `collect_feature_summary` boundary.
- **Files**: `tests/cross_cutting/misc/test_acceptance_support.py`.

## Test Strategy

- Mandatory: T001 (inverted characterization), T002 (regression #4891), T005 (e2e ok=False).
- Commands (use the pre-built venv, never a bare `uv run`):
  - `PWHEADLESS=1 .venv/bin/python -m pytest tests/characterization/test_trio_pure_cores.py tests/cross_cutting/misc/test_acceptance_support.py -q`
  - Regression watch: `PWHEADLESS=1 .venv/bin/python -m pytest tests/integration/test_accept_matrix_coord_partition.py tests/integration/test_placement_partition_golden_path.py -q`
  - Typecheck/lint: `.venv/bin/python -m mypy src/specify_cli/acceptance/gates_core.py` (strict per config); `.venv/bin/ruff check src/specify_cli/acceptance/gates_core.py`; `.venv/bin/ruff format --check src/specify_cli/acceptance/gates_core.py`.

## Risks & Mitigations

- **Risk**: recording only skipped/blocked leaves `ok=True`. **Mitigation**: append an
  `activity_issue` (verified load-bearing).
- **Risk**: breaking a legitimate no-lanes shape. **Mitigation**: none exists on 4.0 (DD-4);
  coord golden-path tests guard it.
- **Risk**: partition confusion (coord-aware read). **Mitigation**: explicitly rejected (DD-2);
  read stays primary.

## Review Guidance

- Verify RED→GREEN: T001/T002 red on `main`, green on the WP's final commit.
- Confirm no coord-aware read introduced; confirm `merge` untouched.
- Confirm `ruff`/`ruff format`/`mypy --strict` clean and complexity ≤15.

## Activity Log

- 2026-09-25T13:30:00Z – system – Prompt created.
