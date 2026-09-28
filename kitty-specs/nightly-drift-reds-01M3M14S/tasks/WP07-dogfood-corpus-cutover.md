---
work_package_id: WP07
title: Dogfood corpus cutover
dependencies:
- WP06
requirement_refs:
- FR-006
planning_base_branch: issue-5258-nightly-drift-reds
merge_target_branch: issue-5258-nightly-drift-reds
branch_strategy: Planning artifacts for this mission were generated on issue-5258-nightly-drift-reds. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5258-nightly-drift-reds unless the human explicitly redirects the landing branch.
subtasks:
- T020
phase: Phase 1 - Drift remediation
history:
- at: '2026-09-28T14:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: kitty-specs/
create_intent: []
execution_mode: planning_artifact
model: ''
owned_files:
- kitty-specs/doctrine-org-init-from-template-01KXNA6P/**
- kitty-specs/org-init-template-security-remediation-01KY4S90/**
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP07 – Dogfood corpus cutover

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

**R9:** cut over both un-flipped dogfood missions with the canonical migration (precedent `9f4105ee3`).

## Subtasks

- **T020** From a standalone checkout (a linked worktree re-anchors the run), first dry-run, then apply:
  - `spec-kitty migrate backfill-runtime-state --mission doctrine-org-init-from-template-01KXNA6P`
  - `spec-kitty migrate backfill-runtime-state --mission org-init-template-security-remediation-01KY4S90`

  Require `verify_ok: true` for both. Only the 4 sanctioned files may change; diff-check that nothing else moved.

## Validation

- `tests/specify_cli/migration/test_dogfood_corpus_backfilled.py`
- `tests/architectural/test_archive_root_byte_identical.py`

## Activity Log

- 2026-09-28T14:00:00Z – system – Prompt created.
