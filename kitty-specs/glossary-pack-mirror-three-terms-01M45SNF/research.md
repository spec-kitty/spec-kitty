# Research: Mirror three glossary terms into the built-in pack

Phase 0 detail lives in [research/code-grounding.md](research/code-grounding.md). Decisions:

- **Decision**: edit both files by hand and append the terms at the end.
  **Rationale**: neither file is generated; the parity gate requires both.
  **Alternatives considered**: pack-only plus `_MISSION_ADDED_SURFACES` registration (rejected: the issue and the precedent mirror into the seed).
- **Decision**: status `active`, confidence `0.9`.
  **Rationale**: the glossary DRG builder keeps only active senses; `draft` would not resolve.
  **Alternatives considered**: `draft` to echo `candidate` (rejected for that reason).
- **Decision**: "do not use" guidance as a definition passage plus `synonyms_to_avoid`.
  **Rationale**: the schema has no dedicated field; `synonyms_to_avoid` is the established metadata slot.
  **Alternatives considered**: `banned_synonyms` (rejected: inert slot under the inert-slot baseline).
- **Decision**: pack text cites ADR ids and `docs/context/` entries, never issue numbers or `src/` paths.
  **Rationale**: shrink-only provenance ratchet on built-in pack files.
