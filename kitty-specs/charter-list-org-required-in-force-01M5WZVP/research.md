# Research: charter list shows org-required ids in force (#6417)

Discovery lives in the research Mission:
[`kitty-specs/charter-list-org-required-research-01M5WZQH/research.md`](../charter-list-org-required-research-01M5WZQH/research.md)
(root cause, fixture drift, consumer list, red-first tests). Plan-phase decisions:

- **Decision**: availability comes from `ActiveCharterManager.list_available_detailed` over the
  full org chain (`org_root_chain=`). **Rationale**: it is the scan `charter list --all` renders,
  so a required id the listing calls in force also shows as available in the layer view.
  **Alternatives**: `IdentityIndex.knows` (skips files without a declared id); `resolve_effective_sets`
  (refuses `skill`, builds the doctrine service for non-directive kinds).
- **Decision**: in force = floor ∩ `PackContext.effective_ids(kind, available)`.
  **Rationale**: the one effective-set authority (ADR `2026-10-19-1` Decision 2); floor beats deny
  through `load_denied`. **Alternatives**: floor minus deny computed in the CLI (a second
  computation, refused by ruling 1).
- **Decision**: an unprovided required id is not named (Decision Moment `01M5WZW16V06ARQ43WD31D7M5F`).
- **Decision**: `schema_version` is the string `"2"` (charter-area convention, research D3).
- **Decision**: fix the scenario fixture (`directives/`, valid directive) rather than relax the
  in-force rule. **Rationale**: the committed fixture's rule is a catalog miss for every reader.
