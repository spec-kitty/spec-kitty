---
work_package_id: WP02
title: Staleness inventory and retired-surface gate
dependencies:
- WP01
requirement_refs:
- FR-009
- FR-010
- FR-011
- FR-012
- FR-013
- FR-014
- FR-015
- NFR-001
- NFR-002
- NFR-004
- NFR-005
- C-003
- C-004
planning_base_branch: issue-6939-readme-rename-and-audit
merge_target_branch: issue-6939-readme-rename-and-audit
branch_strategy: Planning artifacts for this mission were generated on issue-6939-readme-rename-and-audit. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6939-readme-rename-and-audit unless the human explicitly redirects the landing branch.
subtasks:
- T008
- T009
- T010
- T011
- T012
- T013
phase: Phase 2 - Audit
history:
- at: '2026-11-12T22:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: scripts/docs/
create_intent:
- docs/changelog/unreleased/6939-section-indexes-readme-and-docs-audit.changed.md
- scripts/retired_surfaces.py
- scripts/docs/staleness_audit.py
- scripts/docs/retired_surface_gate.py
- scripts/docs/retired_surface_burndown.yaml
- tests/docs/test_staleness_audit.py
- tests/docs/test_retired_surface_gate.py
execution_mode: code_change
model: ''
owned_files:
- scripts/retired_surfaces.py
- scripts/docs/staleness_audit.py
- scripts/docs/retired_surface_gate.py
- scripts/docs/retired_surface_burndown.yaml
- scripts/docs/check_docs_freshness.py
- tests/docs/test_staleness_audit.py
- tests/docs/test_retired_surface_gate.py
- tests/docs/test_check_docs_freshness.py
- tests/architectural/test_no_retired_subsystems.py
- tests/architectural/_baselines.yaml
- tests/architectural/test_ratchet_baselines.py
- .github/workflows/ci-router.yml
- Makefile
- tests/architectural/test_p1_planted_regression.py
- docs/changelog/unreleased/6939-section-indexes-readme-and-docs-audit.changed.md
- tests/ci/test_docs_lint_job.py
- tests/release/ci_retirement_scrub.json
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – Staleness inventory and retired-surface gate

## Load the agent profile first

Use `/spk-charter-profile-load` with `implementer-ivan` (role `implementer`).

## Objectives & Success Criteria

- `python -m scripts.docs.staleness_audit --out <dir>` writes the inventory of every published living page and the per-section page lists, byte for byte reproducible (SC-004, NFR-001).
- One retired-surface authority, `scripts/retired_surfaces.py`, read by `tests/architectural/test_no_retired_subsystems.py`, the gate and the inventory (FR-010).
- `python -m scripts.docs.retired_surface_gate` is green on the tree, red on a planted mention and on a stale burn-down entry (SC-005); it runs in the always-on `docs-lint` job.
- The burn-down list's size is a shrink-only ratchet in `tests/architectural/_baselines.yaml`; every entry names one of #7522–#7528.
- The Mission's `audit/` holds the dated inventory snapshot (under 200 KB) and the page lists; a changelog fragment records the Mission.

## Context & Constraints

- Plan D-6, D-7, D-8. Follow the `documentation-curation-audit` tactic (`spec-kitty charter context --action implement` or the built-in pack).
- The docs-lint job runs no pytest: the gate is a script there, its tests live under `tests/docs`.
- No silent allowlist; no gate weakened.

## Subtasks

- **T008** Red-first tests (commit alone first).
- **T009** Retired-surface authority.
- **T010** Inventory module and page lists.
- **T011** Gate, burn-down, ratchet, freshness sub-check.
- **T012** CI wiring and pins.
- **T013** Snapshot, page lists, changelog fragment.

## Test strategy

`tests/docs`, `tests/ci/test_docs_lint_job.py`, the architectural gates named in the plan, actionlint on `ci-router.yml`, ruff and mypy --strict on touched modules. Run every gate on committed state.

## Activity Log

- 2026-11-12: prompt generated.
