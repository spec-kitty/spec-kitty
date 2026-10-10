---
work_package_id: WP04
title: Pack-tier token single authority
dependencies: []
requirement_refs:
- FR-012
- FR-013
- FR-014
- C-001
- C-003
- NFR-001
- NFR-003
planning_base_branch: feat/charter-kind-tier-vocab-closeout
merge_target_branch: feat/charter-kind-tier-vocab-closeout
branch_strategy: Planning artifacts for this mission were generated on feat/charter-kind-tier-vocab-closeout. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into feat/charter-kind-tier-vocab-closeout unless the human explicitly redirects the landing branch.
subtasks:
- T050
- T051
- T052
- T053
- T054
- T055
- T056
- T057
phase: Phase 4 - Pack-tier vocabulary single authority
history:
- at: '2026-10-09T20:40:00Z'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: ''
authoritative_surface: src/kernel/pack_tiers.py
create_intent:
- src/kernel/pack_tiers.py
- tests/architectural/test_pack_tier_token_single_authority.py
execution_mode: code_change
model: ''
owned_files:
- src/kernel/pack_tiers.py
- src/charter/offering/pack_paths.py
- src/charter/offering/packs/presets.py
- src/charter/offering/pack_skills/validation.py
- src/charter/offering/pack_skills/repository.py
- src/charter/offering/agent_profiles/repository.py
- src/charter/activation/pack_manager.py
- src/specify_cli/cli/commands/charter/list_cmd.py
- src/charter/offering/drg/merge.py
- tests/architectural/test_pack_tier_token_single_authority.py
role: implementer
tags: []
task_type: implement
tracker_refs: []
---

# Work Package Prompt: WP04 – Pack-tier token single authority

Closes #5825 and #5961 (the tier-spelling half; the path half already landed in #3732). Independent of WP02/WP03.

## Objectives & Success Criteria

- One kernel-owned authority for the pack-tier token with a SINGLE spelling `"built-in"` (hyphenated), importable by kernel, charter and specify_cli.
- Every tier-token / rank / provenance site derives from it with the one spelling.
- A net-new architectural gate flags a hand-authored pack-tier token literal under `src/`, with an EMPTY allowlist.
- The on-disk `packs/built-in/` directory name and `kernel._BUILT_IN_DIR_NAME` are UNCHANGED (NFR-003).

## Context & Constraints

Grounded: the tier token has two spellings — `"built-in"` (tier-token sense AND the on-disk dir) and `"builtin"` (tier/rank/provenance). Operator decision: unify the TIER TOKEN on `"built-in"`. The authority must live in `kernel` (only layer importable by all); kernel is a flat package whose modules import siblings freely. `charter.offering.pack_paths.PackTier` becomes a re-export of the kernel symbol. Red-first (C-003); single authority (C-001).

**Grounded sites:**
- `src/charter/offering/pack_paths.py` `PackTier = Literal["built-in","org","project"]` (~92), `_BUILT_IN = "built-in"` (~94), `resolve_pack_root("built-in")` call convention — tier sense.
- `src/charter/offering/packs/presets.py` DUPLICATE `PackTier` (~324).
- `src/charter/offering/pack_skills/validation.py` `Tier = Literal["builtin",...]` (~19, exported ~189); `src/charter/offering/pack_skills/repository.py` `_TIER_RANK {"builtin":0,...}` (~35).
- `src/charter/offering/agent_profiles/repository.py` `_LAYER_RANK {"builtin":0,...}` (~43), `layer="builtin"` (~363, ~1050).
- `src/charter/activation/pack_manager.py` `_LAYER_SEGMENTS = ("built-in","org","project")` (~190).
- `src/specify_cli/cli/commands/charter/list_cmd.py` tier identity map (~112).
- `src/charter/offering/drg/merge.py` layer markers `_tag_source(n,"built-in")` / `conflicting_layers=["built-in",...]`.
- `"builtin"` provenance strings: `context_json.py` (~222), `progressive_disclosure.py` (~225/290/292), `skill_preparation.py` (~163/164/174), `mission_type_profiles.py` (~357/365/729 AND a contradictory `"built-in"` at ~890 — the clearest bug), `runtime/next/_internal_runtime/discovery.py` (~242), `base.py` (~399/436), `agent_profiles/diagnostics.py` (~26), `resolver.py`, `context.py`, `repository_protocol.py` (~45), `context_renderers/selection_block.py`.

**DO NOT change** (NOT tier tokens): `src/kernel/paths.py` `_BUILT_IN_DIR_NAME` (~39, the directory), `offering/provenance.py` env token, `drg/org_pack_config.py` `_BUILTIN_PACK_NAME` (the `pack.yaml name:` field), `drg/models.py` "built-in graph" prose, and any `kind_vocabulary.py` `parts[0] == "built-in"` tier-CHILD check only if it is a directory-name comparison (verify sense before editing).

## Subtasks & Detailed Guidance

- **T050**: audit — grep every `"builtin"`/tier-sense `"built-in"` site and confirm none is persisted or compared against serialized/on-disk data (manifests, snapshots, fixtures, config). A provenance string written into a persisted record that an older reader compares is EXCLUDED from migration with a recorded rationale (this is NFR-003's guard). Report findings before editing.
- **T051**: create `src/kernel/pack_tiers.py` — canonical `PackTier` Literal/enum, ordered tuple `("built-in","org","project")`, a rank map, a provenance-token constant, all single-spelled. Unit tests (RED first) assert the single spelling.
- **T052**: create `tests/architectural/test_pack_tier_token_single_authority.py` — AST gate modelled on `test_charter_kind_vocabulary_single_authority.py` (and `test_built_in_location_authority.py`): flag a hand-authored pack-tier token literal/Literal under `src/` outside the authority; planted self-mutation test; empty `_ALLOWLIST` + `test_allowlist_is_empty`. RED first (migration not yet done).
- **T053–T056**: migrate each site to derive from the authority with the one spelling (`PackTier`/`Tier` → re-export; rank maps → authority rank; `_LAYER_SEGMENTS`/`list_cmd`/`drg` markers → authority tuple/token; provenance strings → authority token). Keep `resolve_pack_root`'s directory lookup working (the token now matches the dir name).
- **T057**: GREEN the tier gate; confirm `test_built_in_location_authority.py`, `test_charter_pack_path_authority.py`, and the kind-vocab gate stay green.

## Test Strategy

- `pytest tests/architectural/test_pack_tier_token_single_authority.py tests/architectural/test_built_in_location_authority.py tests/architectural/test_charter_pack_path_authority.py -q`.
- Owning trees: `tests/charter/ tests/charter_offering/` plus the specify_cli tests for `list_cmd`/skills and the runtime discovery tests (`grep -rl`). Plus `make test-fast` and `pytest tests/architectural/test_no_legacy_terminology.py`.
- Editing pack layout can trip the pack-manifest regen gate — if a pack prompt/layout changed, run `spec-kitty charter pack regenerate-graph` and `spec-kitty doctor charter-packs --json`. (Pure source edits do not.)
- `ruff` + `mypy` clean.

## Review Guidance

- Confirm the authority lives in kernel, one spelling, every site derives; directory name + `_BUILT_IN_DIR_NAME` untouched; T050 audit recorded; the new gate is non-vacuous (planted literal flagged) with an empty allowlist.

## Activity Log

- 2026-10-09T20:40:00Z – system – Prompt created.
