---
work_package_id: WP03
title: Dated report snapshots exempt from literal guards
dependencies: []
requirement_refs:
- FR-002
- FR-003
planning_base_branch: issue-5258-nightly-drift-reds
merge_target_branch: issue-5258-nightly-drift-reds
branch_strategy: Planning artifacts for this mission were generated on issue-5258-nightly-drift-reds. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5258-nightly-drift-reds unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-drift-reds-01M3M14S
base_commit: d1aacecd12c3a0306e29646f11d1d72c4f6cf978
created_at: '2026-09-28T14:01:08.829515+00:00'
subtasks:
- T009
- T010
- T011
phase: Phase 1 - Drift remediation
history:
- at: '2026-09-28T14:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: tests/contract/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/specify_cli/cli/test_decision_command_shape_consistency.py
- tests/contract/test_terminology_guards.py
- docs/development/reference/terminology-exemptions.md
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP03 – Dated report snapshots exempt from literal guards

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

- **R5:** `decision list` is canonical (`989667221`, #3951).
- **R6 and #5187:** the dated `docs/reports/tracer-friction-recon/2026-09-26/` snapshot quotes retired shapes on purpose. Do NOT reword it.
- Exempt `docs/reports/` in both guards, aligned with `ARCHIVE_PATH_PREFIXES` in `tests/architectural/test_no_dead_src_path_literals.py`. Reference that classification; don't invent a third divergent tuple.
- Guard the exemption: assert that `reports/` is absent from `docs/docfx.json` content globs, so the exemption fails loudly if reports are ever published.

## Subtasks

- **T009** `EXPECTED_SUBCOMMANDS` and the non-canonical regex include `list`; update the docstring.
- **T010** Add the prefix exemption plus the docfx guard to both files.
- **T011** Update the narrowness pin in `test_terminology_guards.py` (the exempt tuple now includes `docs/reports/`, while other live `docs/` pages are still scanned). Add a `docs/reports/` line to `terminology-exemptions.md`.

## Validation

- The two owned test files.
- `tests/architectural/test_no_legacy_terminology.py`.
- Any test covering `terminology-exemptions.md` (grep for it).

## Activity Log

- 2026-09-28T14:00:00Z – system – Prompt created.
