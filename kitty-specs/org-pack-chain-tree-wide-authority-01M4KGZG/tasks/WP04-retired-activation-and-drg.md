---
work_package_id: WP04
title: Migration-tier caller + drg.py decision
dependencies: []
requirement_refs:
- FR-001
- FR-002
planning_base_branch: feat/org-pack-chain-tree-wide-authority
merge_target_branch: feat/org-pack-chain-tree-wide-authority
branch_strategy: Planning artifacts for this mission were generated on feat/org-pack-chain-tree-wide-authority. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/org-pack-chain-tree-wide-authority unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-org-pack-chain-tree-wide-authority-01M4KGZG
base_commit: 3d135d769dd6db69b576b3334bb6128fefe2299c
created_at: '2026-10-10T18:56:09.615755+00:00'
subtasks:
- T014
- T015
history:
- created by /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/specify_cli/upgrade/migrations/
create_intent: []
execution_mode: code_change
model: sonnet
owned_files:
- src/specify_cli/upgrade/migrations/_retired_activation.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Load profile `python-pedro` via `/spk-charter-profile-load` before anything else.

## Objective

Migrate the one migration-tier caller and confirm the `charter.drg` facade decision.

## Subtasks

### T014 — `upgrade/migrations/_retired_activation.py:353`
`[*resolve_existing_org_roots(project_path), *_retired_key_org_roots(...)]` → `[*resolve_pack_chain(project_path, strict=False), *_retired_key_org_roots(...)]`. Keep the retired-key splice exactly; the first element set is byte-identical. Import `resolve_pack_chain` directly from `charter.activation.layer_roots`. `_retired_activation` is a frozen migration — preserve its behaviour precisely.

### T015 — confirm `charter.drg` stays frozen (DEC-6012-2)
No edit to `src/charter/drg.py`. Confirm (and note in the review) that: its primitive re-exports (`resolve_existing_org_roots`, `resolve_org_dirs`, `resolve_org_roots`, `load_pack_registry`) stay in place (tests + `resolve_org_dirs` users depend on them), and migrated callers import `resolve_pack_chain` from `charter.activation.layer_roots`, not via drg. This WP does not own `drg.py`; if you believe a re-export is warranted, raise it as a finding rather than editing out-of-map.

## Branch Strategy
Planning base + merge target: `feat/org-pack-chain-tree-wide-authority`. Lane worktree from `lanes.json`.

## Definition of Done
- `_retired_activation.py:353` migrated, retired-key splice intact, behaviour byte-identical.
- `charter.drg` unchanged; decision confirmed in the review note.
- Existing `_retired_activation` / upgrade-migration tests pass; `ruff` clean.

## Risks / reviewer guidance
Reviewer: confirm the migration path still produces the same ordered roots (retired-key entries preserved) and that `_retired_key_org_roots` (iterates retired-key entries, not `registry.packs`) is untouched and not a census hit.
