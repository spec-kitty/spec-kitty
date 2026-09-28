---
work_package_id: WP02
title: CLI-surface product fix and oracle re-pins
dependencies: []
requirement_refs:
- FR-002
planning_base_branch: issue-5258-nightly-drift-reds
merge_target_branch: issue-5258-nightly-drift-reds
branch_strategy: Planning artifacts for this mission were generated on issue-5258-nightly-drift-reds. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5258-nightly-drift-reds unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-drift-reds-01M3M14S
base_commit: d1aacecd12c3a0306e29646f11d1d72c4f6cf978
created_at: '2026-09-28T14:00:51.662251+00:00'
subtasks:
- T004
- T005
- T006
- T007
- T008
phase: Phase 1 - Drift remediation
history:
- at: '2026-09-28T14:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/specify_cli/cli/commands/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/specify_cli/cli/commands/_coordination_doctor.py
- src/specify_cli/cli/commands/mission_type.py
- tests/specify_cli/cli/commands/test_doctor_coordination.py
- tests/specify_cli/cli/commands/test_doctor_cli_surface_golden.py
- tests/specify_cli/cli/commands/test_mission_type_current_fallback_signal.py
- tests/specify_cli/test_audit_tail_readers.py
- tests/specify_cli/invocation/cli/test_dispatch.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP02 – CLI-surface product fix and oracle re-pins

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

- **R4 (FIX-PRODUCT).** `_apply_missing_worktree_fix`'s `else` arm relays `exc.next_step` for a remote-only branch when the finding has no `coord_branch` extra. That text loops the operator back to the refusing `--fix` and omits `git branch <b> origin/<b>`, which is the loop #5113 prevents.
- **R1–R3, R15, R17, R21, R22:** re-pin. **R16:** delete. See the spec verdict table for commit evidence.

## Subtasks

- **T004** Red-first: `@pytest.mark.regression` issue-pinned (#5258) test. A remote-only coordination branch refused without a `coord_branch` extra must yield the ordered steps from `_coord_worktree_missing_remote_only_steps` (contains `git fetch` and `branch <b> origin/<b>`). Show it RED on base. After the fix, convert it into the focused re-pin of R4; do not leave it marked `regression`.
- **T005** Fix: `branch = coord_branch or exc.coordination_branch`, then reclassify on that value. Also add the genuinely-generic case: a local-head branch whose materialization still refuses, where "materialize it now" is present and "git fetch" is absent. Add a test for the main remote-only arm with the `coord_branch` extra present, if none exists.
- **T006** Doctor golden. Add `decisions` to `FROZEN_SUBCOMMANDS`, `EXPECTED_OPTIONS` and `EXPECTED_HELP`, rendered through the file's own `force_wide_help_console` + `normalize_help`. Update the coordination wording (`cf295c58a`) and provenance help (`e8186a911`). Bump the docstring count.
- **T007** `test_mission_type_current_fallback_signal.py`:
  - R15 → fail-closed (exit 1, "not found", no "Active Mission"), invoked twice so it stays deterministic across repeats.
  - Delete R16.
  - R17 → `software-dev` type, so the re-emit loop runs.
  - Remove the dead `"using software-dev as default"` branch in `mission_type.py` (`7a9c35728`) and refresh the module docstring.
- **T008** R21: the envelope is on stderr with `code == DESIGN_STATUS_EVENT_LOG_UNREADABLE` (`dd808bc4b`). R22: `{ok: false, error: {code, message}}` (`45303ca90`).

## Validation

- The five owned test files.
- `tests/specify_cli/cli/commands/test_mission_type*.py`, plus any tests that import `_coordination_doctor` (`grep -rl _coordination_doctor tests`).

## Activity Log

- 2026-09-28T14:00:00Z – system – Prompt created.
