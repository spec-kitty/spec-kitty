# Tasks: Charter Pack level declared in pack.yaml

**Mission**: pack-level-declared-in-pack-yaml-01M4NVEN | **Branch**: issue-6048-pack-level-pack-yaml
**Plan**: [plan.md](./plan.md) · **Spec**: [spec.md](./spec.md)

7 work packages across lanes A–G. Critical path WP01→WP02. WP06 (provenance respell, isolated) and WP07 (docs) run parallel from t0. After WP01: WP02/WP03/WP04/WP05 run in parallel. Dependency DAG: `WP01 → {WP02, WP03, WP04, WP05}`; `WP06`, `WP07` independent.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | ATDD: descriptor level/version/requires_core schema | WP01 | |
| T002 | Add pack_level (reuse kernel PackTier Literal) | WP01 | |
| T003 | Add requires_core (optional, specifier-validated) | WP01 | |
| T004 | Add active_charter/pack_drg + conditional pack_version | WP01 | |
| T005 | New pack_level single-authority gate (empty allowlist) | WP01 | |
| T006 | ATDD: load refusals (MISMATCH/MISSING) | WP02 | |
| T007 | resolve_pack_layout seam (new pack_layout.py) | WP02 | |
| T008 | Route existing filename lookups through the seam | WP02 | |
| T009 | validate branches on declared level | WP02 | |
| T010 | check_pack_level + MISMATCH wiring (position-aware) | WP02 | |
| T011 | PACK_LEVEL_MISSING warn-then-refuse constant | WP02 | |
| T012 | Org-path pack.yaml read (OrgPackConfig, bounded) | WP02 | |
| T013 | ATDD: project-pack backfill migration | WP03 | [P] |
| T014 | Implement migration (config-aware, no mkdir) | WP03 | [P] |
| T015 | Idempotency + non-clobber | WP03 | [P] |
| T016 | Register + wire the migration | WP03 | [P] |
| T017 | ATDD: authored-field gate expects pack_level | WP04 | [P] |
| T018 | built-in pack.yaml += pack_level: built-in | WP04 | [P] |
| T019 | new packs/internal/pack.yaml (org + pointers + id) | WP04 | [P] |
| T020 | internal pack_id drift test | WP04 | [P] |
| T021 | Regenerate + commit built-in manifest (LS-4) | WP04 | [P] |
| T022 | ATDD: regenerate-graph --pack-root | WP05 | [P] |
| T023 | --pack-root on regenerate-graph (write + --check) | WP05 | [P] |
| T024 | Clean-tree level-aware digest (LF-normalized) | WP05 | [P] |
| T025 | Assert snapshot_sha256 untouched (NFR-004) | WP05 | [P] |
| T026 | requires_core checker (core_compat) | WP05 | [P] |
| T027 | Wire + help text | WP05 | [P] |
| T028 | ATDD: get_provenance hyphenated + manifest self-heal | WP06 | [P] |
| T029 | Respell emitter + derive displays from kernel (LS-1) | WP06 | [P] |
| T030 | Mappers + serialized surfaces respell | WP06 | [P] |
| T031 | Drop NFR-003 carve-out + rewrite docstrings | WP06 | [P] |
| T032 | Update dogfood agent_profiles_manifest.json | WP06 | [P] |
| T033 | Update ~7 serialized-contract tests | WP06 | [P] |
| T034 | Update ~24 in-memory assertion tests | WP06 | [P] |
| T035 | Fold ADR 2026-10-11-2 (Decision §2 aligned) | WP07 | [P] |
| T036 | ADR consequences: retire NFR-003 + cross-version note | WP07 | [P] |
| T037 | docs/context charter.md + governance.md | WP07 | [P] |
| T038 | CHANGELOG entry | WP07 | [P] |
| T039 | Finalize diagram/README + close #6049 | WP07 | [P] |

## Work Packages

### WP01 — Descriptor schema + pack_level single-authority gate (lane A, root)
- **Goal**: new `pack.yaml` fields + the empty-allowlist pack_level gate. **Priority**: P1. **Deps**: none.
- **Independent test**: `tests/charter_offering/test_pack_descriptor_level.py` + `tests/architectural/test_pack_level_single_authority.py`.
- Subtasks: T001 T002 T003 T004 T005 → [WP01 prompt](./tasks/WP01-descriptor-schema-and-gate.md)

### WP02 — Load refusals + validate branch-on-level + resolution seam (lane B)
- **Goal**: MISMATCH/MISSING, level-branched validate, the one layout seam. **Priority**: P1. **Deps**: WP01.
- **Independent test**: `test_pack_level_load_refusals.py`, `test_pack_layout.py`, `test_org_pack_level_read.py`.
- Subtasks: T006 T007 T008 T009 T010 T011 T012 → [WP02 prompt](./tasks/WP02-load-refusals-validate-seam.md)

### WP03 — Project-pack backfill migration (lane C)
- **Goal**: backfill pack.yaml for project packs. **Priority**: P2. **Deps**: WP01.
- **Independent test**: `tests/upgrade/test_pack_level_backfill.py`.
- Subtasks: T013 T014 T015 T016 → [WP03 prompt](./tasks/WP03-project-pack-backfill-migration.md)

### WP04 — In-repo descriptors + authored-field gate + manifest regen (lane D)
- **Goal**: built-in += level; new internal pack.yaml; gate key set; regen manifest. **Priority**: P1. **Deps**: WP01.
- **Independent test**: `test_pack_manifest_no_author_edit.py`, `test_internal_pack_identity.py`, `test_packaging_safety.py`.
- Subtasks: T017 T018 T019 T020 T021 → [WP04 prompt](./tasks/WP04-in-repo-descriptors-and-authored-gate.md)

### WP05 — Vendoring tooling (lane E)
- **Goal**: --pack-root, requires_core checker, clean-tree digest. **Priority**: P2. **Deps**: WP01.
- **Independent test**: `test_regenerate_graph_pack_root.py`, `test_pack_clean_digest.py`, `test_requires_core_check.py`.
- Subtasks: T022 T023 T024 T025 T026 T027 → [WP05 prompt](./tasks/WP05-vendoring-tooling.md)

### WP06 — Provenance respell + tier-token gate extension (lane F, ISOLATED)
- **Goal**: builtin→built-in unified on kernel.pack_tiers, one coherent change. **Priority**: P1. **Deps**: none (parallel t0).
- **Independent test**: `tests/charter/`, `tests/charter_offering/`, `test_pack_tier_token_single_authority.py`, `tests/specify_cli/tool_surface/`.
- Subtasks: T028 T029 T030 T031 T032 T033 T034 → [WP06 prompt](./tasks/WP06-provenance-respell-unify.md)

### WP07 — ADR fold + docs + diagram (lane G, fold last)
- **Goal**: ADR 2026-10-11-2, docs/glossary/CHANGELOG, diagram/README, close #6049. **Priority**: P3. **Deps**: none.
- **Independent test**: `test_no_legacy_terminology.py` + docs-lint/freshness/inventory checks.
- Subtasks: T035 T036 T037 T038 T039 → [WP07 prompt](./tasks/WP07-adr-fold-docs-diagram.md)

## MVP scope
WP01 + WP02 (schema + load/validate) is the functional MVP of #6048; WP06 (provenance unification) and WP05 (#6046 tooling) are the other two pillars.

## Dependencies
```
WP01 ──┬── WP02
       ├── WP03
       ├── WP04
       └── WP05
WP06  (independent, isolated lane, from t0)
WP07  (independent, docs, folds last)
```
