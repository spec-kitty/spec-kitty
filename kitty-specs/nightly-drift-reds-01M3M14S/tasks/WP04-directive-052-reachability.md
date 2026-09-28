---
work_package_id: WP04
title: DIRECTIVE_052 reachability and corpus-count ratchet
dependencies: []
requirement_refs:
- FR-004
- FR-005
planning_base_branch: issue-5258-nightly-drift-reds
merge_target_branch: issue-5258-nightly-drift-reds
branch_strategy: Planning artifacts for this mission were generated on issue-5258-nightly-drift-reds. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-5258-nightly-drift-reds unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-drift-reds-01M3M14S
base_commit: d1aacecd12c3a0306e29646f11d1d72c4f6cf978
created_at: '2026-09-28T14:01:24.702326+00:00'
subtasks:
- T012
- T013
- T014
phase: Phase 1 - Drift remediation
history:
- at: '2026-09-28T14:00:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: src/charter/offering/drg/
create_intent: []
execution_mode: code_change
model: ''
owned_files:
- src/charter/offering/drg/migration/extractor.py
- packs/built-in/*.graph.yaml
- packs/built-in/pack-manifest.yaml
- tests/doctrine/drg/migration/test_extractor_projection.py
- tests/specify_cli/charter_lint/checks/test_orphan.py
- tests/specify_cli/bulk_edit/test_occurrence_map_field_paths.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---
# Work Package Prompt: WP04 – DIRECTIVE_052 reachability and corpus-count ratchet

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

- **R7 (FIX-PRODUCT, consumer tier):** DIRECTIVE_052 has no incoming edge, so `charter lint` reports it as orphaned for every consumer. Add a curated `procedure:disciplined-defect-diagnosis --suggests--> directive:DIRECTIVE_052` edge in `_CURATED_ARTIFACT_EDGES`, following the DISCIPLINED_REFACTORING precedent. Do NOT add a profile `requires` edge. The orphan exact-set test must pass unchanged at `{DIRECTIVE_035, DIRECTIVE_039}`.
- **R8:** re-pin the SC-011 counts after R7 lands. The governance count must be derived by re-running the inventory, never guessed. Known drift so far: +1 governance (`3e3bcb4da`), −2 raw (`414bbe89b`, #5203). Remove `python-conventions` from the two raw sets.

## Subtasks

- **T012** Add the curated edge. Correct the extractor comment about 052 being de-orphaned by its outbound edges.
- **T013** Run `spec-kitty doctrine regenerate-graph`. Add ledger entry (23) in `test_extractor_projection.py`. Confirm the `requires` histogram is unchanged.
- **T014** Re-pin R8. Name both sha steps in the history comment. Note that the test pins live pack counts (a drift magnet).

## Validation

- The three owned test files.
- The pack-manifest / regenerate-graph gate test(s): grep for `pack-manifest` under `tests/doctrine` and `tests/charter`.
- `tests/charter/test_reconciler_promotion.py`.
- `tests/cross_cutting/packaging/test_packaging_safety.py`.

## Activity Log

- 2026-09-28T14:00:00Z – system – Prompt created.
