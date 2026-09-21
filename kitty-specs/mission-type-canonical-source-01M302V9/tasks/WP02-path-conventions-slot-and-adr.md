---
work_package_id: WP02
title: path_conventions doctrine slot + VALID_PATH_KEYS to charter + ADR
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-009
- NFR-002
planning_base_branch: fix/mission-type-canonical-source-3831
merge_target_branch: fix/mission-type-canonical-source-3831
branch_strategy: Planning artifacts for this mission were generated on fix/mission-type-canonical-source-3831. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into fix/mission-type-canonical-source-3831 unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-mission-type-canonical-source-01M302V9
base_commit: 2a13aef93e1f857cd62e25417572d840add56968
created_at: '2026-09-20T19:58:10.307205+00:00'
subtasks:
- T010
- T011
- T012
- T013
- T014
phase: Phase 2 - Canonical schema home
history:
- at: '2026-09-20T19:20:00Z'
  actor: system
  action: Prompt generated for mission-type-canonical-source
agent_profile: python-pedro
authoritative_surface: src/charter/offering/missions/
create_intent:
- docs/adr/3.x/2026-09-20-1-canonical-mission-type-source.md
- tests/charter/test_path_conventions_slot.py
execution_mode: code_change
model: ''
owned_files:
- src/charter/offering/missions/models.py
- docs/adr/3.x/2026-09-20-1-canonical-mission-type-source.md
- tests/charter/test_path_conventions_slot.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP02 – path_conventions slot + VALID_PATH_KEYS relocation + ADR

## ⚡ Do This First: Load Agent Profile
Load `python-pedro` via `/ad-hoc-profile-load`.

## Objectives & Success Criteria
Create the one genuinely-new schema home (`path_conventions`) on the charter mission-type model and make `charter` the canonical home for `VALID_PATH_KEYS`; author the ADR. This is tidy-first foundation — no consumer rewire yet.

## Context & Constraints
- Canonical source is charter `ResolvedMissionType`; C-001 forbids `charter → specify_cli`. `VALID_PATH_KEYS` is added to charter here (the `specify_cli` copy is removed + importers repointed in WP04 — transient dual-home is green).
- `path_conventions` is net-new (zero hits in `src/charter/` or `packs/built-in/`) → the pack-manifest regen gate fires; fold the regen output in this commit.

## Subtasks & Detailed Guidance
### Subtask T010 – path_conventions field
- Add a `path_conventions` field to `src/charter/offering/missions/models.py` (mission-type schema) and the doctrine mission-type artifact schema. A type may declare none (→ downstream no-op).
### Subtask T011 – VALID_PATH_KEYS home
- Add `VALID_PATH_KEYS` + the path-convention validator to `charter/offering/missions/models.py` as canonical. Do NOT yet delete the `specify_cli/mission.py` copy (WP04).
### Subtask T012 – Tests
- Unit tests: slot parse/validate; a type with no conventions; validator behaviour.
### Subtask T013 – ADR
- `docs/adr/3.x/2026-09-20-1-canonical-mission-type-source.md`: canonical source = `ResolvedMissionType`; legacy `specify_cli/mission.py` resolver retired; `path_conventions` new slot; **name the `Mission` collision** (`specify_cli/mission.py` vs `charter/offering/missions/models.py:137`). Companion to 2026-07-14-2 / 2026-07-15-1; reconciles 2026-08-28-1. (Adjust the date-seq in the filename to the next free ADR number for 2026-09-20.)
### Subtask T014 – Regen
- Run `.venv/bin/spec-kitty doctrine regenerate-graph`; commit the regen output here.

## Test Strategy
- `.venv/bin/python -m pytest tests/charter/test_path_conventions_slot.py -q`; run the pack-manifest regen gate test if present.

## Risks & Mitigations
- Layer violation → keep the constant DOWN in charter; no `charter → specify_cli` import.

## Review Guidance
- Confirm the ADR names both `Mission` classes and the regen output is committed.

## Activity Log
- 2026-09-20T19:20:00Z – system – Prompt created.
