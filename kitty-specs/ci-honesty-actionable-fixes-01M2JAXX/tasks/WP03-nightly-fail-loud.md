---
work_package_id: WP03
title: '#4212: nightly performance-and-e2e fails loud on a red suite'
dependencies: []
requirement_refs:
- FR-006
planning_base_branch: fix/ci-honesty-actionable-fixes
merge_target_branch: fix/ci-honesty-actionable-fixes
branch_strategy: Planning artifacts for this mission were generated on fix/ci-honesty-actionable-fixes. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/ci-honesty-actionable-fixes unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-ci-honesty-actionable-fixes-01M2JAXX
base_commit: bd1941af491239b73429c52af678eca67333b4cf
created_at: '2026-09-15T13:18:20.836095+00:00'
subtasks:
- T011
- T012
- T013
- T014
phase: Phase 1 - CI honesty fixes
history:
- at: '2026-09-15T11:45:58Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: .github/workflows/ci-nightly.yml
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- .github/workflows/ci-nightly.yml
- tests/architectural/test_performance_marker_guard.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP03 – #4212 nightly fail-loud

## ⚡ Do This First: Load Agent Profile

Use the `/ad-hoc-profile-load` skill to load the agent profile specified in the frontmatter before parsing the rest of this prompt.

- **Profile**: `python-pedro`
- **Role**: `implementer`
- **Agent/tool**: `claude`

---

## Markdown Formatting

Wrap HTML/XML tags in backticks. Use language identifiers in code blocks.

## Objectives & Success Criteria

The nightly `performance-and-e2e` (and interpreter-matrix) job must FAIL when any suite exits
non-zero, while still running every suite. Done when:

- `tests/architectural/test_performance_marker_guard.py` pins "suite steps are fail-loud" — RED on
  base `36d866d4fa`, GREEN on the fix.
- A failing suite makes the job result `failure` (not `success`); run-all `if: always()` /
  `fail-fast: false` preserved.
- `ruff` / `ruff format --check` clean (YAML + any test edits); no new suppressions.

## Context & Constraints

- Design: `research.md` (Decision 4), `work/ci-honesty-4437/lenses/C-verdict-and-nightly.md` (#4212).
- Mechanism: `ci-nightly.yml:92-98` (perf), `:100-106` (e2e), `:149-155` (interpreter) run under
  `set +e` and end on `echo "::notice::…exit=$?"` — the step exits `0` (the echo), discarding pytest's
  exit. `nightly-summary` (`:256-267`) only echoes `needs.*.result` and never fails; and because the
  steps exit 0, `needs.performance-and-e2e.result` is `success` regardless.
- Fix: capture each suite's `$?` into `$GITHUB_ENV` (keep the annotation), then add a terminal
  `if: always()` step in the job that `exit 1`s if any captured code is non-zero.
- **Preserve run-all (C-003)**: keep `set +e` + `if: always()` + `fail-fast: false` so every suite
  still runs and the COMPLETE failure set is surfaced (`ci-nightly.yml:16-24` intent). The guard
  `test_performance_marker_guard.py:254-255` already requires `if:always()`/`fail-fast:false` — the new
  assertion must coexist with it.
- **OUT OF SCOPE (C-001)**: nightly-only; do NOT touch per-PR workflows, the router, aggregate, or
  fleet-verdict.

## Branch Strategy

- **Planning base branch**: `main` · **Merge target branch**: `main`
- Execution worktree allocated per computed lane from `lanes.json`.

## Subtasks & Detailed Guidance

### Subtask T011 – RED: nightly suite steps are fail-loud (commit FIRST)
- **Steps**: In `tests/architectural/test_performance_marker_guard.py` add
  `test_nightly_suite_steps_are_fail_loud`: for each suite step running `pytest`, assert its captured
  exit is consumed by a downstream step/job that can `exit 1` (i.e. the step does NOT terminate on a
  bare `echo "…exit=$?"` that discards the code). RED on base.
- **Files**: `tests/architectural/test_performance_marker_guard.py`.
- **Notes**: Parses `NIGHTLY_WORKFLOW` (`:41`); coexist with the `:254-255` if:always/fail-fast guards.

### Subtask T012 – Capture suite exit codes
- **Steps**: In `ci-nightly.yml` for perf (`:92-98`), e2e (`:100-106`), interpreter (`:149-155`):
  `code=$?; echo "PERF_EXIT=$code" >> "$GITHUB_ENV"; echo "::notice::performance suite exit=$code"`
  (and analogous for e2e/interpreter). Keep `set +e` so later suites still run.
- **Files**: `.github/workflows/ci-nightly.yml`.

### Subtask T013 – Terminal fail-loud step
- **Steps**: Add an `if: always()` final step in `performance-and-e2e` (and `interpreter-matrix`)
  that reads the captured codes and `exit 1`s if any is non-zero. Preserve uploaded xunit artefacts
  (`:108-113`).
- **Files**: `.github/workflows/ci-nightly.yml`.
- **Notes**: Alternatively let `nightly-summary` (`:256`) fail when any `needs.*.result != 'success'`
  once the jobs actually go red — pick one, keep run-all semantics.

### Subtask T014 – Verify red→green
- **Steps**: `pytest tests/architectural/test_performance_marker_guard.py -q` (green on fix, red on
  base); confirm the `:254-255` run-all guards still pass; `ruff check . && uv run --frozen ruff format --check .`.
- **Notes**: Record red-on-base/green-on-fix in the Activity Log.

## Test Strategy

`tests/architectural/test_performance_marker_guard.py` (workflow-lint) is the RED-first pin. No new
test file needed (extend existing) → no new-file arch battery.

## Risks & Mitigations

- **Breaking run-all** by dropping `set +e` → do NOT; capture-and-aggregate instead.
- LOW overall risk: nightly-only, off the per-PR blocking path.

## Review Guidance

- RED-first test red on base, green on final; run-all guards coexist.
- A failing suite now makes the job red; every suite still runs.
- No per-PR / router / aggregate / fleet-verdict edits (C-001).

## Activity Log

- 2026-09-15T11:45:58Z – system – Prompt created.
