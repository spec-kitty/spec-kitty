# Research — pack-level-declared-in-pack-yaml

Phase 0. Consolidates the pre-spec grounding (three CodeGraph reconnaissance passes), the adversarial architect review, and operator rulings. Every decision below was resolved before spec; this file is the rationale record.

## R-1 — `pack_level` type: reuse `kernel.pack_tiers.PackTier`
- **Decision**: type `pack_level` as the existing `kernel.pack_tiers.PackTier` Literal; introduce no new enum.
- **Rationale**: `kernel.pack_tiers` already owns the three level tokens (`built-in`/`org`/`project`) under an empty-allowlist AST gate (`test_pack_tier_token_single_authority.py`). A second enum in `charter.offering.packs` would duplicate naming authority and could trip that gate. `kernel < charter`, so `charter` may import it. Operator ruling (Q1).
- **Alternatives considered**: a new `PackLevel(StrEnum)` deriving members by reference from kernel (gate-safe but a naming duplication the architect flagged); rejected per operator.

## R-2 — Fold the governing ADR into this PR
- **Decision**: carry `docs/adr/4.x/2026-10-11-2-a-pack-declares-its-level-in-pack-yaml.md` in this PR; close #6049; align its Decision §2 to "kernel owns the tokens; the descriptor reuses the Literal; no second enum."
- **Rationale**: the ADR is docs-only in unmerged PR #6049; folding it makes this PR cite a file present in its own diff (single authority). Operator ruling (Q2). Filename is `-2-` (the `-1-` slot that day is the archive-freeze ADR).
- **Alternatives**: depend on #6049 merging first (cleaner provenance but a merge-order coupling); land independently citing pending (fragile). Rejected per operator.

## R-3 — Fold #5992 (provenance respell), no data migration
- **Decision**: respell the 3-tier artifact provenance/layer value `"builtin"` → `"built-in"`, unify on `kernel.pack_tiers`; no consumer data migration.
- **Rationale**: verified that **no read-back code compares a persisted layer value to `"builtin"`** — every live comparison runs on freshly computed `get_provenance()` output, so emitter + comparisons move together. The one persisted carrier (`.kittify/agent_profiles_manifest.json` `source_layer`) is validated as a non-empty string and regenerated each projection → self-heals. Operator ruling (Q3).
- **Scope fence (C-002)**: only the 3-tier provenance vocabulary. NOT the `builtin|pack` skill-origin vocabulary (`skills/manifest.py`, `registry.py`) nor the `"builtin:"` command-target prefix (`pack_skills/models.py`).
- **Test surface**: ~7 serialized-contract files (`test_manifest.py`, `test_portable_provenance.py`, `test_heal_provenance.py`, `test_charter_rendering.py`, `test_context.py`, `test_doctrine_asset.py`, `test_profiles_activation.py`) + ~30 in-memory assertion files.
- **Alternatives**: defer #5992 to a follow-up (architect's and my original recommendation, safe but leaves the split); rejected per operator in favour of unification now.

## R-4 — `packs/internal/` gets its own `pack.yaml`; descriptor declares layout
- **Decision**: add `packs/internal/pack.yaml` (`pack_level: org`, pinned `pack_id`, `active_charter: org-charter.yaml`, `pack_drg: drg/fragment.yaml`). `org-charter.yaml` remains the pack's active-charter *content*.
- **Rationale**: internal is an org-tier pack (ADR 2026-08-16-3, Option B). Operator ruling: `pack.yaml` is the identity/level descriptor; `org-charter.yaml` is content. The descriptor's `active_charter`/`pack_drg` pointers mean layout is declared, not located by hard-coded filename. Operator ruling (follow-ups).
- **Consequences**: the org-pack load path must gain a `pack.yaml` read; `pack_version` becomes required only for built-in (FR-005) so internal need not author one; internal's `pack_id` is drift-pinned (mirror `test_pack_id_identity`).

## R-5 — Clean-tree digest: enumerated-known-files / LF-normalized
- **Decision**: add a NEW digest reusing the `builtin_manifest` enumerated-known-files, LF-normalized approach; leave `snapshot_sha256` and its two remote-snapshot callers byte-unchanged.
- **Rationale**: must be identical across a `git archive` export, a working checkout (with `__pycache__`), and an installed copy. `git ls-files` fails on a `.git`-less export; an rglob-minus-ignore-list is fail-open. Enumerating declared artifact kinds ignores noise by construction and reuses tested code. `snapshot_sha256` correctly hashes an installed exact copy (raw bytes, full tree) for the install-record path — repurposing it would corrupt that semantics (NFR-004).
- **Alternatives**: `git ls-files` (rejected: no index on export); rglob-minus-ignore (rejected: brittle, fail-open).

## R-6 — `PACK_LEVEL_MISSING` warn-then-refuse behind a tracked switch
- **Decision**: WARN now when `pack_level` is absent; gate the hard refuse behind a single module-level constant (default = warn), flipped by a tracked follow-up.
- **Rationale**: the ADR grants org packs a one-release deprecation window; this mission invents no release anchor (C-006). The constant makes both the warn and refuse paths testable now (flip the constant in a test).

## R-7 — Gate collisions are deliverables, not regressions
- **Decision**: update `test_pack_manifest_no_author_edit` (built-in `pack.yaml` key set += `pack_level`) and extend `test_pack_tier_token_single_authority` (cover the unified spelling, drop the NFR-003 carve-out, keep empty allowlist); add a new `test_pack_level_single_authority` gate.
- **Rationale**: both existing gates explicitly freeze today's shape (the exact `{pack_id,pack_version,parent_pack,name}` key set; the `"builtin"` provenance carve-out). The mission deliberately shifts those contracts, so the gate edits are in-scope deliverables; an implementer must not treat the resulting red as a pre-existing failure.

## R-8 — Supply-chain posture
- **Decision**: no new third-party dependency is added beyond `packaging` (already available, used for version specifiers). No install-time supply-chain control is triggered.
- **Rationale**: `requires_core` validation uses the version-specifier machinery already present; no new package install. DIRECTIVE_051 posture: nothing to surface beyond this note. No adversarial supply-chain challenge required (no dependency decision of consequence).
