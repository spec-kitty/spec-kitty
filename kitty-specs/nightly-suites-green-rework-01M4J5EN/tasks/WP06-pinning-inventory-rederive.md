---
work_package_id: WP06
title: Pinning-rule inventory re-derivation (#5989)
dependencies: []
requirement_refs:
- FR-008
planning_base_branch: fix/nightly-suites-green-rework
merge_target_branch: fix/nightly-suites-green-rework
branch_strategy: Planning artifacts for this mission were generated on fix/nightly-suites-green-rework. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/nightly-suites-green-rework unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-nightly-suites-green-rework-01M4J5EN
base_commit: 30f1aaa9a449e423285c0f7dd8a9c1c6db87b3e4
created_at: '2026-10-10T06:17:38.404160+00:00'
subtasks:
- T018
- T019
phase: Phase 2 - Derived artifact
history:
- at: '2026-10-10T05:45:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/release/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- tests/release/pinning_rule_inventory.json
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP06 – Pinning-rule inventory re-derivation (#5989)

## ⚡ Do This First: Load Agent Profile
Use `/spk-charter-profile-load` to load `python-pedro` (implementer, claude).

## Objectives & Success Criteria

`test_inventory_is_reproducible_by_rerunning_the_derivation` (nightly `interpreter-3.13-shard-3`, #5989) is RED: a new pinning rule (the `retiring-step` rule declared in `tests/specify_cli/charter_packs/test_pack_validator_org_endpoints.py`) exists in-tree but `tests/release/pinning_rule_inventory.json` was not re-derived. The test warns: *"A rule added to the tree since the last derivation must be dispositioned, not regenerated away."*

Done when: the committed inventory equals a fresh `derive_pinning_inventory.py` run, with the new `retiring-step` rule explicitly dispositioned (FR-008).

## Context & Constraints
- **C-003**: disposition the new rule — do not delete/regenerate it away.
- The derivation script is the canonical source: `scripts/ci/derive_pinning_inventory.py` (do not hand-edit the json except for the disposition fields the script expects).

## Subtasks
- **T018** — Run `python3 scripts/ci/derive_pinning_inventory.py` (or the `--write` form it documents) to regenerate the inventory; inspect the diff — it should add the `retiring-step` rule entry. Supply the disposition the rule requires (per how existing rules are dispositioned in the json) so the new rule is accounted for, not dropped.
- **T019** — Verify `test_inventory_is_reproducible_by_rerunning_the_derivation` green (committed == fresh derivation). Red-first shown via the current staleness failure.

## Branch Strategy
Planning base / merge target: `fix/nightly-suites-green-rework`. Lane from `lanes.json`.

## Validation
```bash
PWHEADLESS=1 .venv/bin/python -m pytest -p no:cacheprovider -q \
  "tests/release/test_pinning_inventory_fresh.py"
```

## Definition of Done
Inventory reproducible; new `retiring-step` rule dispositioned (not removed); test green.

## Reviewer Guidance (opus)
Confirm the new rule is dispositioned (present with a disposition), not regenerated-away; confirm the json matches a fresh derivation.
