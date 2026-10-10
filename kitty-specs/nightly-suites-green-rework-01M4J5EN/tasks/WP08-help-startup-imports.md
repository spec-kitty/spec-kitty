---
work_package_id: WP08
title: --help startup import shave + budget (#5991)
dependencies: []
requirement_refs:
- FR-010
- FR-011
planning_base_branch: fix/nightly-suites-green-rework
merge_target_branch: fix/nightly-suites-green-rework
branch_strategy: Planning artifacts for this mission were generated on fix/nightly-suites-green-rework. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/nightly-suites-green-rework unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-suites-green-rework-01M4J5EN
base_commit: d9e98cb1f37aedd42723a8100d85d129f8cd7a2d
created_at: '2026-10-10T06:30:49.983459+00:00'
subtasks:
- T022
- T023
- T024
- T025
phase: Phase 2 - Performance
history:
- at: '2026-10-10T05:45:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/cli/commands/
create_intent:
- tests/performance/test_help_import_surface.py
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/specify_cli/cli/commands/next_cmd.py
- tests/performance/test_help_import_surface.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP08 – `--help` startup import shave + budget (#5991)

## ⚡ Do This First: Load Agent Profile
Use `/spk-charter-profile-load` to load `python-pedro` (implementer, claude).

## Objectives & Success Criteria

`test_help_stays_inside_its_startup_budget` (nightly `performance`, #5991) fails: `spec-kitty --help` ratio 3.085 > `STARTUP_RATIO_LIMIT` 2.90. There is a real eager-import regression from the two reworks: `src/specify_cli/cli/commands/next_cmd.py:57-59` imports at module scope `runtime.next._runtime_pkg_notice` and `runtime.next.decision`, which drag `charter.activation.*` (~70ms, doctrine-to-charter), `runtime.next._internal_runtime.schema` (~143ms, next rework), and `status.dup_key_repair` (~19ms) onto the `--help` path — which activates nothing.

Done when:
- FR-010: those module-scope imports are deferred into the command function bodies (or TYPE_CHECKING), and a new import-absence test asserts the chains are NOT imported on `spec-kitty --help`.
- FR-011: the startup-budget test passes on the nightly runner at the operator-confirmed limit.

## Context & Constraints
- **C-005**: the final limit value (keep 2.90 vs bump) is an OPERATOR/CI-owned calibration decision measured on the nightly runner. Do NOT change `tests/_perf_helpers.py` `STARTUP_RATIO_LIMIT` in this WP, and do NOT set a number from a local timing series. Shave the imports at root; let CI re-measure. If after the shave CI still exceeds 2.90, surface it to the operator — do not bump the limit unilaterally.
- FR-011 is no-op passable by a bare limit bump; the FR-010 import-absence test is its positive control — that is the deliverable that proves the shave is real.
- `next_cmd.py` already defers most runtime imports into function bodies (e.g. lines 116, 190, 529, 1073, 1127). Lines 57-59 are the leak; move them the same way. Preserve public behavior and type checking (use `TYPE_CHECKING` for annotations, lazy accessors for `VALID_RESULT_VALUES` / `AnalysisCurrency` / `AnalysisVerdict`).

## Subtasks
- **T022** — Red-first: write the import-absence test (T024) first so it is RED on the base — run `spec-kitty --help` in a subprocess (production entry point) and assert that `charter.activation`, `runtime.next._internal_runtime.schema`, `runtime.next.decision`, and `status.dup_key_repair` are absent from `sys.modules` / the import trace.
- **T023** — Defer the `next_cmd.py:57-59` module-scope imports into the command function bodies (and `TYPE_CHECKING` for annotations). Verify the `next` command behavior is unchanged (its own tests still green).
- **T024** — Land the import-absence test at `tests/performance/test_help_import_surface.py`, exercising the real `--help` entry point (subprocess, not a helper). It must go GREEN after T023.
- **T025** — Run the existing startup-budget test locally for signal only (a single read, not a series); record the local ratio in the Activity Log and explicitly flag that the authoritative pass/limit is an operator/CI decision (C-005). Do NOT edit the limit.

## Branch Strategy
Planning base / merge target: `fix/nightly-suites-green-rework`. Lane from `lanes.json`.

## Validation
```bash
PWHEADLESS=1 .venv/bin/python -m pytest -p no:cacheprovider -q \
  tests/performance/test_help_import_surface.py
# next-command regression (behavior unchanged):
PWHEADLESS=1 .venv/bin/python -m pytest -p no:cacheprovider -q tests/specify_cli/runtime -k next
```

## Definition of Done
Import-absence test green and non-vacuous (exercises `--help` subprocess); `next` behavior unchanged; `STARTUP_RATIO_LIMIT` untouched; local ratio + operator-decision flag recorded; `ruff`/`mypy` clean.

## Reviewer Guidance (opus)
Confirm the imports are genuinely deferred (not merely reordered), the import-absence test uses the real `--help` entry point, `next` behavior is unchanged, and the perf limit was NOT bumped (C-005 — operator owns that).
