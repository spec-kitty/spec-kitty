---
work_package_id: WP06
title: Provenance respell (builtin→built-in) unified on kernel.pack_tiers + tier-token gate extension (ISOLATED lane)
dependencies: []
requirement_refs:
- FR-016
- FR-017
- FR-019
- NFR-001
- NFR-002
- C-002
planning_base_branch: issue-6048-pack-level-pack-yaml
merge_target_branch: issue-6048-pack-level-pack-yaml
branch_strategy: Planning artifacts for this mission were generated on issue-6048-pack-level-pack-yaml. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-6048-pack-level-pack-yaml unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-pack-level-declared-in-pack-yaml-01M4NVEN
base_commit: 8d179634494a092407dbde168447642259acea61
created_at: '2026-10-11T16:46:33.705941+00:00'
subtasks:
- T028
- T029
- T030
- T031
- T032
- T033
- T034
phase: Phase 1 - Provenance unification (parallel)
history:
- at: '2026-10-11T16:20:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: src/charter/offering/
create_intent: []
execution_mode: code_change
model: claude-sonnet-5-5
owned_files:
- src/kernel/pack_tiers.py
- src/charter/offering/base.py
- src/charter/offering/agent_profiles/repository.py
- src/charter/offering/pack_skills/repository.py
- src/charter/offering/pack_skills/validation.py
- src/charter/offering/assets/repository.py
- src/charter/activation/context_json.py
- src/charter/activation/progressive_disclosure.py
- src/charter/activation/mission_type_profiles.py
- src/charter/activation/skill_preparation.py
- src/specify_cli/cli/commands/_charter_pack_health.py
- src/specify_cli/cli/commands/_charter_pack_collect.py
- src/specify_cli/cli/commands/profiles_cmd.py
- src/specify_cli/invocation/registry.py
- src/specify_cli/mission_loader/validator.py
- src/specify_cli/tool_surface/profiles/projection.py
- src/runtime/next/_internal_runtime/discovery.py
- .kittify/agent_profiles_manifest.json
- tests/architectural/test_pack_tier_token_single_authority.py
- tests/specify_cli/tool_surface/profiles/test_manifest.py
- tests/charter/test_portable_provenance.py
- tests/specify_cli/upgrade/migrations/test_heal_provenance.py
- tests/cli/commands/test_charter_rendering.py
- tests/charter/test_context.py
- tests/specify_cli/cli/commands/test_doctrine_asset.py
- tests/specify_cli/invocation/cli/test_profiles_activation.py
- tests/charter_offering/test_base_org_layer.py
- tests/charter_offering/test_service_org_layer.py
- tests/charter_offering/agent_profiles/test_register_overlay.py
- tests/charter_offering/assets/test_repository.py
- tests/charter_offering/pack_skills/test_repository.py
- tests/charter_offering/test_profile_repository.py
- tests/charter_offering/test_profile_diagnostics.py
- tests/charter_offering/test_pack_relocation_doctor_gate.py
- tests/charter_offering/agent_profiles/test_drupal_dries_profile.py
- tests/charter_offering/drg/test_override_policy_predicates.py
- tests/integration/test_pack_enhances_partial_fields.py
- tests/charter/test_mission_type_profile_override.py
- tests/charter/test_mission_type_profiles.py
- tests/charter/test_active_charter_service_lineage_accessor.py
- tests/charter/test_skill_preparation.py
- tests/charter/context_renderers/test_include_selector_widening.py
- tests/charter/test_context_selection_render.py
- tests/runtime/test_resolver_unit.py
- tests/specify_cli/tool_surface/test_model.py
- tests/specify_cli/tool_surface/profiles/test_projection.py
- tests/specify_cli/tool_surface/test_projection_collision_precedence.py
- tests/specify_cli/test_doctor_charter_packs_health.py
- tests/specify_cli/cli/commands/test_doctor_charter_packs_collisions.py
role: implementer
tags: []
tracker_refs: []
---

## ⚡ Do This First: Load Agent Profile

Load `python-pedro` via `/spk-charter-profile-load`. Read `plan.md` — the squad-refinements items **D (lockstep)** and the **WP06 scope-fence enumeration** are the two most load-bearing things in this entire mission. Read `research.md` R-3 (no data migration, verified). This lane is ISOLATED and parallel from t0.

## Objective

Respell the 3-tier artifact PROVENANCE/LAYER value `"builtin"` → `"built-in"` and unify it onto `kernel.pack_tiers`, so one spelling serves both the tier token and provenance. This removes the NFR-003 carve-out. **It must land as one coherent change (LS-1): the gate goes red the instant the emitter is respelled unless the whole set moves together AND each display derives from the authority.**

## ⛔ Scope fence (C-002) — read before editing
- **IN (respell these — the 3-tier provenance/layer vocabulary)**: `base.py::_provenance`/`get_provenance` emitter; `agent_profiles/repository.py::_LAYER_RANK`; `pack_skills/repository.py::_TIER_RANK` (3-tier — IN scope even though it sits beside the fenced skill-origin vocab); `_charter_pack_health.py::_LAYER_ORDER`; `invocation/registry.py` routing frozenset (`_LAYER_BUILTIN`); `pack_skills/validation.py::Tier` Literal; mappers in `skill_preparation.py`, `profiles_cmd.py`, `_charter_pack_collect.py`; `mission_type_profiles.py` provenance default; `assets/repository.py` compare; `mission_loader/validator.py` `precedence_tier` compare; `discovery.py` builtin tier tuple; serialized surfaces `context_json.py`, `progressive_disclosure.py`, `projection.py`; and the dogfood `.kittify/agent_profiles_manifest.json`.
- **OUT (DO NOT TOUCH)**: `skills/manifest.py` / `skills/registry.py` `origin: "builtin"|"pack"` skill-origin vocabulary; `pack_skills/models.py::BUILTIN_TARGET_PREFIX = "builtin:"` command-target prefix; `retrospective/reader.py::_provenance` (a different, non-artifact-layer provenance); any symbol NAME containing "builtin" (`_resolve_builtin_collision`, `builtin_roots`, migration module names) — only quoted 3-tier layer string VALUES move.

## Subtasks

### T028 — ATDD anchor (RED first)
`tests/charter_offering/test_base_org_layer.py` (extend) or a focused new assertion: `get_provenance()` of a built-in artifact returns `"built-in"`; serialized surfaces (`charter context --json` `source`, `asset list --json` `tier`, projection `source_layer`) carry `"built-in"`. Plus NFR-001 anchor: a pre-respell `.kittify/agent_profiles_manifest.json` carrying `"source_layer": "builtin"` still parses and self-heals. Commit RED first.

### T029 — Respell the emitter + derive every display from kernel.pack_tiers (LS-1)
Respell `base.py::_provenance` to emit `kernel.pack_tiers.BUILT_IN`. Then convert every IN-scope display (`_LAYER_RANK`, `_TIER_RANK`, `_LAYER_ORDER`, routing frozenset, `Tier` Literal) to **DERIVE from `kernel.pack_tiers`** (comprehension/reference over `PACK_TIERS`), NOT a hand-respelled literal — this is what keeps the single-authority gate's allowlist empty. Do NOT add anything to any allowlist.

### T030 — Mappers + serialized surfaces
Update the provenance→display/tier mappers and the serialized surfaces so they emit/compare `"built-in"`. The two CLI display re-spellings (`profiles_cmd.py`, `_charter_pack_collect.py`) that mapped `"builtin"→"built-in"` become identity/no-op.

### T031 — Drop the NFR-003 carve-out + rewrite docstrings (FR-019)
In `test_pack_tier_token_single_authority.py`: remove/retire `test_gate_leaves_the_frozen_builtin_provenance_vocabulary_alone` and the carve-out language in the module docstring. Rewrite the `kernel/pack_tiers.py` Scope-note docstring (the lines asserting the provenance value is deliberately NOT folded) to state the fold is done and the spelling is now unified. Keep the gate's `_ALLOWLIST` empty and its non-vacuity floor intact — the gate must now also catch a hand-authored `"built-in"` provenance restatement.

### T032 — Update the dogfood manifest (FR-017)
Update the committed `.kittify/agent_profiles_manifest.json` so every `source_layer` reads `"built-in"` (keeps the repo's own tree clean; the file self-heals on next projection anyway).

### T033 — Update serialized-contract tests (~7 files)
Update the serialized-contract assertions that pin the old spelling: `test_manifest.py`, `test_portable_provenance.py`, `test_heal_provenance.py`, `test_charter_rendering.py`, `test_context.py`, `test_doctrine_asset.py`, `test_profiles_activation.py`.

### T034 — Update in-memory assertion tests (~24 files)
Update the in-memory `== "builtin"` / `layer == "builtin"` / `provenance_of(...) == "builtin"` / `source_layers=["builtin"]` assertions across the files listed in `owned_files` (the `tests/charter_offering/*`, `tests/charter/*`, `tests/runtime/*`, `tests/specify_cli/tool_surface/*`, `tests/specify_cli/*doctor*` set) to `"built-in"`.

## Definition of Done
- One coherent change: no WP boundary is red. The main single-authority gate AND the carve-out retirement pass together; allowlist still empty; the gate now catches a planted `"built-in"` provenance restatement.
- Scope fence honoured: the `builtin|pack` skill-origin, the `"builtin:"` prefix, and `retrospective/reader.py` are UNCHANGED (grep-verify no accidental edit).
- No consumer data migration; a pre-respell manifest parses + self-heals (NFR-001).
- ruff/format/mypy clean (NFR-006).

## Tests to run (targeted)
`.venv/bin/python -m pytest tests/charter/ tests/charter_offering/ tests/architectural/test_pack_tier_token_single_authority.py tests/specify_cli/tool_surface/ tests/runtime/test_resolver_unit.py tests/specify_cli/test_doctor_charter_packs_health.py -q`

## Reviewer guidance
The top risk is the scope fence — grep the diff for any edit to the OUT list and reject if present. Verify displays DERIVE from `kernel.pack_tiers` (not re-spelled literals) so the allowlist stays empty. Verify the NFR-003 carve-out and docstrings are retired explicitly, not silently. Verify no WP-boundary red (single commit for the respell + gate).

## Branch Strategy
Planning/merge base `issue-6048-pack-level-pack-yaml`; isolated lane worktree per `lanes.json`.
Implement with: `spec-kitty agent action implement WP06 --agent <name> --mission pack-level-declared-in-pack-yaml-01M4NVEN`
