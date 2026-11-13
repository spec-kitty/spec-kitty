---
work_package_id: WP01
title: Rename the section indexes to README.md
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-007
- FR-008
- FR-015
- NFR-003
- NFR-004
- NFR-005
- C-001
- C-002
- C-005
planning_base_branch: issue-6939-readme-rename-and-audit
merge_target_branch: issue-6939-readme-rename-and-audit
branch_strategy: Planning artifacts for this mission were generated on issue-6939-readme-rename-and-audit. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6939-readme-rename-and-audit unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
- T007
phase: Phase 1 - Rename
history:
- at: '2026-11-12T22:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: implementer-ivan
authoritative_surface: scripts/docs/
create_intent:
- tests/docs/test_section_index_basename.py
execution_mode: code_change
model: ''
owned_files:
- docs/**
- site/moves.yaml
- site/dockitty-contract.json
- site/link-debt.json
- scripts/docs/_dockitty_contract.py
- scripts/docs/moves_ledger.py
- scripts/docs/site_redirects.py
- scripts/docs/rename_reconcile.py
- scripts/docs/freshen_adr_inventory.py
- scripts/docs/touched_set_gates.py
- scripts/docs/site_built_check.py
- scripts/docs/dockitty_frontmatter_migration.py
- scripts/ci/regen_docs_index.py
- scripts/ci/generated_docs_surfaces.py
- scripts/ci/check_generated_docs_untouched.py
- .github/workflows/docs-index-regen.yml
- AGENTS.md
- src/charter/offering/templates/diagrams/README.md
- src/specify_cli/missions/documentation/templates/plan-template.md
- tests/docs/test_section_index_basename.py
- tests/docs/test_moves_ledger.py
- tests/docs/test_one_index_per_folder.py
- tests/docs/test_dockitty_frontmatter_migration.py
- tests/docs/test_dockitty_frontmatter_shape.py
- tests/docs/test_related_validator.py
- tests/docs/test_site_redirects.py
- tests/docs/test_freshen_adr_inventory.py
- tests/docs/test_touched_set_gates.py
- tests/docs/test_site_scaffold.py
- tests/docs/test_dockitty_contract.py
- tests/docs/test_adr_readme_prose.py
- tests/docs/test_architecture_docs_consistency.py
- tests/docs/test_artifact_placement_seam_page.py
- tests/docs/test_docs_structural_lint.py
- tests/docs/test_docs_index_regenerates_cleanly.py
- tests/docs/test_tracker_egress_upgrade_note_3108.py
- tests/docs/test_versioned_docs_integrity.py
- tests/ci/test_check_generated_docs_untouched.py
- tests/ci/test_regen_docs_index.py
- tests/architectural/test_retired_charter_vocabulary.py
- tests/architectural/test_gate_selection_authority.py
- tests/charter_offering/test_wp_authoring_contract_roundtrip.py
- tests/contract/test_terminology_guards.py
- tests/glossary/test_canonical_promotion.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP01 – Rename the section indexes to README.md

## Load the agent profile first

Use `/spk-charter-profile-load` with `implementer-ivan` (role `implementer`).

## Objectives & Success Criteria

- No `index.md` under `docs/`; 59 section indexes renamed to `README.md` with `git mv` (SC-001).
- `site/moves.yaml` records each rename (`/x/index.html -> /x/README.html`, ref `#6939`); the ledger reads a return into a route as superseding the earlier move away.
- `INDEX_BASENAMES == ('README',)`; `site/dockitty-contract.json` regenerated.
- `site/legacy-redirects.json` byte-identical; `python -m scripts.docs.site_redirects --check` clean (SC-002).
- `dockitty-check-links --strict` clean (SC-003). `relative_link_fixer --check` adds no dead link: it reports 10, all present at base 7e9113ce2 (12 there; the rename fixed 2).
- Every reader names `README.md`; the generated-surface guard accepts the era tables' move.
- ADR `2026-10-31-1` gains `## Amendment 2026-11-12 (section indexes renamed)`, appended only.

## Context & Constraints

- Spec and plan: `kitty-specs/readme-rename-and-docs-audit-01M78WZM/spec.md`, `plan.md` (D-1 to D-5).
- Charter: `.kittify/charter/charter.md` (ATDD-first: the red test commit comes first).
- Reuse from branch `issue-6939-rename-section-indexes-to-readme` (#7040, closed): `tests/docs/test_section_index_basename.py` with its planted control, the rename map (minus `docs/templates`, removed in #6943) and the `freshen_adr_inventory.py` basename switch.
- Immutable bodies change link targets only (ADR D-7). The bot-owned generated surfaces are not edited.

## Subtasks

- **T001** Red-first tests (commit alone first): the basename ratchet (reused), `collapse` with a return entry, `is_index_rename`, the narrowed basename, the redirect map unchanged by an index rename.
- **T002** `git mv` the 59 files.
- **T003** Ledger entries and the `moves_ledger` change; `rename_reconcile` and `test_moves_ledger` use `is_index_rename`.
- **T004** `_dockitty_contract.INDEX_BASENAMES`, `site_contract` regeneration, `site_redirects` legacy fold and rule 3.
- **T005** Link rewrite from the ledger's `#6939` pairs; immutable diff verification.
- **T006** Readers and real-path tests.
- **T007** ADR amendment.

## Test strategy

`uv run --frozen pytest tests/docs -n 4 --dist loadfile --tb=line -q`, `tests/ci/test_check_generated_docs_untouched.py`, `tests/ci/test_regen_docs_index.py`, `python -m scripts.docs.site_redirects --check`, the doc-kitty frontmatter and link gates, ruff, mypy --strict on touched modules. Run every gate on committed state.

## Activity Log

- 2026-11-12: prompt generated.
