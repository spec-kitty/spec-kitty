# Contracts — charter-kind-tier-vocab-closeout

This mission hardens single-authority vocabularies; its executable "contracts"
are **architectural gates**, not request/response schemas. The binding contracts are:

- `tests/architectural/test_charter_kind_vocabulary_single_authority.py` — the
  artifact-kind vocabulary single-authority gate (R1'/R4/R5/R6 added; empty allowlist).
- `tests/architectural/test_charter_facades_reexport_offering.py` — facade re-export
  identity gate, now covering non-class values (#5836).
- `tests/architectural/test_pack_tier_token_single_authority.py` — net-new pack-tier
  token single-authority gate (empty allowlist).
- `src/charter/offering/artifact_kinds.py` — the `ArtifactKind` authority (now carrying
  `has_layered_repository`; `core`/`CORE_KIND_PLURALS` retired).
- `src/kernel/pack_tiers.py` — the pack-tier token authority (single `"built-in"` spelling).

See `../design-decisions.md` (DD-1..DD-4) for the material choices.
