---
work_package_id: WP01
title: Colour-independent in-process CLI output
dependencies: []
requirement_refs:
- FR-001
planning_base_branch: issue-5258-nightly-drift-reds
merge_target_branch: issue-5258-nightly-drift-reds
branch_strategy: Planning artifacts for this mission were generated on issue-5258-nightly-drift-reds. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5258-nightly-drift-reds unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-drift-reds-01M3M14S
base_commit: d1aacecd12c3a0306e29646f11d1d72c4f6cf978
created_at: '2026-09-28T13:59:58.694880+00:00'
subtasks:
- T001
- T002
- T003
phase: Phase 1 - Drift remediation
history:
- at: '2026-09-28T14:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: tests/conftest.py
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/conftest.py
- tests/specify_cli/invocation/cli/test_complete.py
- tests/cli/test_events_tail.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP01 – Colour-independent in-process CLI output

## ⚡ Do This First: Load Agent Profile

Load the `implementer-ivan` profile (`/ad-hoc-profile-load`) and behave according to its guidance before parsing the rest of this prompt.

## Context & Constraints

- Spec verdict table: `kitty-specs/nightly-drift-reds-01M3M14S/spec.md` (R1–R23). The charter binds you: `.kittify/charter/charter.md` (DIRECTIVE_041: stale → re-pin, stub → delete, valid → fix the product; never skip, xfail, quarantine or retry-to-green).
- Sibling-owned paths (never edit): `src/specify_cli/consolidation/**`, `tests/integration/**`, `.github/workflows/ci-nightly.yml`, `scripts/ci/nightly_escalation.py`, `tests/charter/test_consistency_check.py`.
- NO_FULL_HEAVY_SUITES_IN_MISSION: run only the files listed under Validation.
- Every re-pin comment names the causing commit sha. New code passes `ruff check`, `ruff format --check`, and complexity ≤15.

## Branch Strategy

- **Strategy**: single_branch (lane-less) on `issue-5258-nightly-drift-reds`
- **Planning base branch**: issue-5258-nightly-drift-reds
- **Merge target branch**: issue-5258-nightly-drift-reds (PR → `main`)

## Objectives & Success Criteria

R10–R14 (`tests/specify_cli/cli/commands/test_mission_close_guard.py`) fail on GitHub runners because `typer/rich_utils.py` freezes `FORCE_TERMINAL=True` at import time when `GITHUB_ACTIONS`, `FORCE_COLOR` or `PY_COLORS` is set. The autouse `_plain_cli_console_seam` only toggles `CliConsole`. The fix goes at the harness level, not per test. SC-002: the file passes under `GITHUB_ACTIONS=true` and under `FORCE_COLOR=1`. `NO_COLOR` alone is NOT a fix.

## Subtasks

- **T001** Record the red first: `GITHUB_ACTIONS=true .venv/bin/python -m pytest tests/specify_cli/cli/commands/test_mission_close_guard.py -p no:randomly -q` shows 5 failed.
- **T002** In `_plain_cli_console_seam`, pin `typer.rich_utils.FORCE_TERMINAL = False` and `COLOR_SYSTEM = None`, and restore both in `finally`. Explain why in a comment (#5258).
- **T003** Refresh the notes in `tests/specify_cli/invocation/cli/test_complete.py` and `tests/cli/test_events_tail.py` that say the seam does not reach Typer's console. Keep their per-test helpers, which are harmless.

## Validation

- The mission-close guard file under: no env, `GITHUB_ACTIONS=true`, and `FORCE_COLOR=1`.
- `tests/specify_cli/cli/commands/test_help_snapshot.py`, `tests/specify_cli/invocation/cli/test_complete.py`, `tests/cli/test_events_tail.py` under `GITHUB_ACTIONS=true`.
- Grep for tests that expect `\x1b[` from in-process runners, and run them.

## Activity Log

- 2026-09-28T14:00:00Z – system – Prompt created.
