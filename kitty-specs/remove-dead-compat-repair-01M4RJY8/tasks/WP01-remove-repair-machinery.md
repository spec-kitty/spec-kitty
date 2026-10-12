---
work_package_id: WP01
title: Remove the
dependencies: []
requirement_refs:
- FR-001
- FR-002
- FR-003
- NFR-001
- NFR-002
- SC-001
planning_base_branch: issue-6095-dead-compat-repair
merge_target_branch: issue-6095-dead-compat-repair
branch_strategy: Planning artifacts for this mission were generated on issue-6095-dead-compat-repair. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6095-dead-compat-repair unless the human explicitly redirects the landing branch.
base_branch: issue-6095-dead-compat-repair
base_commit: cb780be8770a4775f16b2e490b251705a8afb0b5
created_at: '2026-10-12T17:45:05Z'
subtasks:
- T001
- T002
- T003
- T004
- T005
phase: Phase 1 - Remove dead minting path
history: []
agent_profile: python-pedro
authoritative_surface: src/specify_cli/migration/backfill_runtime_state.py
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/migration/backfill_runtime_state.py
role: implementer
tags: []
tracker_refs: []
---

# WP01 — Remove the #2985 compatibility-repair machinery

Delete the globally-unreachable repair path, following the dead-reference chain in
`research/code-grounding.md` §4. Remove: `_plan_compatibility_repairs`,
`_verify_compatibility_repairs`, `_misaligned_seed_wps`, `_runtime_repair_delta`,
`_repair_scalar_value`, `_compatibility_repair_at`, `_repair_id`,
`_stream_without_compatibility_repairs`, `COMPATIBILITY_REPAIR_ACTOR`. Fold out the two
live call sites (`_backfill_runtime_state_locked`, `verify_backfill`). Simplify
`_is_migration_actor` (drop repair branch) and `_wp_events` (drop `include_seeds`).

KEEP (live): `_legacy_contract_carriers`, `_matches_legacy_contract`, `_LegacyCarrier`,
`_verify_expected_seed_events`, `_verify_claim_slot_witnesses`, `_stream_without_migration`,
`_wp_history_floor`.

**Validation**: `grep -rn` removed symbols in src/ → none; mypy --strict + ruff clean on the
file; module imports.
