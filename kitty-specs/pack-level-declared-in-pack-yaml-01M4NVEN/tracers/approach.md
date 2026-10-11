# Approach — pack-level-declared-in-pack-yaml

Seeded at planning (Standing Order #3). Append as the mission runs.

## Shape of the work (8 pillars → candidate lanes)

1. **Schema** — `PackDescriptor` += `pack_level` (PackTier), `requires_core`, `active_charter`, `pack_drg`; `pack_version` level-conditional. (FR-001..005)
2. **Load refusals** — `PACK_LEVEL_MISMATCH` / `PACK_LEVEL_MISSING` (warn now). (FR-006/007)
3. **Validate + resolution seam** — branch on declared level; one `(pack_root, descriptor) → paths` seam. (FR-008/009)
4. **Migration** — project-pack backfill, config-aware, skip built-in/internal. (FR-010)
5. **In-repo descriptors** — built-in += level; new internal `pack.yaml`. (FR-011/012)
6. **#6046 tooling** — `--pack-root`, `requires_core` check hook, clean-tree digest. (FR-013..015)
7. **#5992 provenance unify** — respell + gate extension + ~7 wire + ~30 in-memory test updates. (FR-016..019)
8. **Gates/docs/ADR/diagram** — new pack_level gate, ADR fold, docs/glossary/CHANGELOG, diagram+README. (FR-020..023)

## Sequencing notes

- Schema (1) is the foundation; refusals (2), validate (3), in-repo descriptors (5) and migration (4) depend on it.
- Provenance unify (7) depends on the gate work and is the largest test surface — isolate it so its ~37-file test churn does not entangle the schema lanes.
- ATDD-first: each lane lands a failing-first acceptance test before implementation (charter C-011).
- The diagram + README (FR-023) are already drafted on the branch (diagram-daisy) — fold into the docs lane, review as a mission artifact.

## Test strategy (charter C-005 / NO_FULL_HEAVY_SUITES_IN_MISSION)

- Baseline `make test-fast`; plus `tests/charter/` and `tests/charter_offering/` in full (both own the touched code).
- Named gates only: `test_charter_kind_vocabulary_single_authority`, `test_pack_manifest_no_author_edit`, `test_pack_tier_token_single_authority`, `test_packaging_safety`, the new pack_level gate.
- Upgrade migration tests for FR-010.
- No full `tests/architectural/` sweep, no `make test-full`.
