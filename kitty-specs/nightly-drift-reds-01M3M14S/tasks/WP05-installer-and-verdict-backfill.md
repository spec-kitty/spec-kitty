---
work_package_id: WP05
title: Installer and verdict-backfill oracles
dependencies: []
requirement_refs:
- FR-007
planning_base_branch: issue-5258-nightly-drift-reds
merge_target_branch: issue-5258-nightly-drift-reds
branch_strategy: Planning artifacts for this mission were generated on issue-5258-nightly-drift-reds. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5258-nightly-drift-reds unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-drift-reds-01M3M14S
base_commit: d1aacecd12c3a0306e29646f11d1d72c4f6cf978
created_at: '2026-09-28T14:01:41.277243+00:00'
subtasks:
- T015
- T016
- T017
phase: Phase 1 - Drift remediation
history:
- at: '2026-09-28T14:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: tests/specify_cli/skills/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- tests/specify_cli/skills/test_installer.py
- tests/specify_cli/skills/test_installer_global_reassess_convergence.py
- tests/migration/test_verdict_provenance_backfill.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP05 – Installer and verdict-backfill oracles

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

- **R18/R19:** the canonical `kernel.locks.machine_file_lock` (`c206e7d2d`, #4714) re-touches `home/.kittify/cache/.agent-skills.lock`. Tolerate exactly that: same sha256 and mode, only `mtime_ns` may move.
- **R20:** RE-PIN, not delete. Without rebuild, a concurrent peer now converges too. Bisect the causing commit with `git bisect` or `git archive` snapshots; do NOT quote `ed6d34e75` unverified. Add a call-count spy (`calls == 1`) on `rebuild_global_assets` to the with-rebuild test, so the rebuild seam is proven used. Refresh the module docstring.
- **R23 (#5279):** add the causal rework hops (`in_progress → for_review → in_review`) between the backfilled rejection and the real approval. Add a positive pin: a bare `in_review → approved` after the backfilled rejection, with no rework, resolves `changes_requested` (#4990, events 10.4.0). Use unique event ids.

## Validation

- The three owned files.
- `tests/specify_cli/upgrade/test_verdict_provenance_backfill_migration.py`.

## Activity Log

- 2026-09-28T14:00:00Z – system – Prompt created.
