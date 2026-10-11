# Implementation Plan: Charter Pack level declared in pack.yaml

**Branch**: `issue-6048-pack-level-pack-yaml` | **Date**: 2026-10-11 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/pack-level-declared-in-pack-yaml-01M4NVEN/spec.md`

## Summary

Make every Charter Pack declare its `pack_level` (and, optionally, its charter/DRG layout) in `pack.yaml`; refuse a declared level that disagrees with the configured position; branch validation on the declared level through one resolution seam; unify the pack-tier/provenance vocabulary under the single `kernel.pack_tiers` authority (folding #5992's provenance respell); and add the core tooling (`regenerate-graph --pack-root`, `requires_core`, a clean-tree drift digest) that lets open-packs vendor the built-in pack. Technical approach is settled (see `tracers/design-decisions.md`): reuse the kernel `PackTier` Literal (no new enum), additive optional descriptor fields, a config-aware backfill migration, and gate updates as first-class deliverables.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: pydantic v2 (`PackDescriptor`/`PackManifest` models), ruamel.yaml (pack.yaml I/O), typer (CLI), `packaging` (version-specifier validation for `requires_core`)
**Storage**: On-disk pack files (`pack.yaml`, `pack-manifest.yaml`, `*.graph.yaml`, `org-charter.yaml`, `drg/fragment.yaml`); `.kittify/config.yaml` (org-pack registry); `.kittify/charter-packs/` (project pack)
**Testing**: pytest (`tests/charter/`, `tests/charter_offering/`, `tests/specify_cli/`, `tests/kernel/`, `tests/upgrade/`, named `tests/architectural/` gate files); mypy --strict; ruff + ruff format
**Target Platform**: Cross-platform CLI (Linux, macOS, Windows 10+)
**Project Type**: single (library + CLI; enforced import chain `kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli`)
**Performance Goals**: `charter pack validate` / `regenerate-graph` < 2s typical (NFR-005)
**Constraints**: single-authority invariant (empty-allowlist gate, NFR-002); clean-tree digest deterministic across git-archive/worktree/installed (NFR-003); install-record path byte-unchanged (NFR-004); no consumer data migration (NFR-001); zero ruff/mypy issues, no new suppressions (NFR-006); respell scope-fenced to the 3-tier provenance vocabulary (C-002)
**Scale/Scope**: ~8 source modules changed + 1 new migration; ~7 serialized-contract test files + ~30 in-memory test files updated for the respell; 3 architectural gates touched + 1 new

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority (#1)** — ✅ central to the mission: `kernel.pack_tiers` is the ONE owner for both the tier token and (newly) the artifact provenance spelling; `pack_level` reuses its Literal; a new empty-allowlist gate (FR-020) and the extended tier-token gate (FR-019) enforce it. No second authority is introduced.
- **Architectural alignment (DIRECTIVE_001)** — ✅ respects the `kernel <- charter <- specify_cli` chain (`charter` imports `kernel`, never the reverse). The descriptor stays in `charter.offering.packs`; the migration lives in `specify_cli/upgrade/migrations/`.
- **DDD + tiered rigour** — ✅ core domain logic (descriptor schema, load refusals, resolution seam, provenance) gets full rigour; the diagram/docs lane is glue.
- **ATDD-first (C-011)** — ✅ every WP lands a failing-first acceptance test (RED on base, GREEN on final) before implementation; reviewer verifies red→green.
- **Campsite cleaning / Boy-Scout (DIRECTIVE_025, brownfield)** — ✅ opening each lane, campsite-clean only the *touched* surfaces (Sonar/complexity on `pack_descriptor.py`, `pack_validator.py`, `base.py`); fold only domain-matched debt; separate tidy-first commits from functional change.
- **Terminology canon** — ✅ "Mission" not "Feature"; `pack_level`/`built-in` canonical; US-spelling (`organization`-style terms avoided per the ADR's rejected-names note).
- **No full heavy suites in mission work (NO_FULL_HEAVY_SUITES_IN_MISSION)** — ✅ targeted files + named gates only; CI owns the full sweeps.
- **Gate discipline (DIRECTIVE_043)** — ✅ the new pack_level gate starts with an empty allowlist in the same mission that introduces it (non-vacuous, self-mutation-tested).

No violations → Complexity Tracking empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/pack-level-declared-in-pack-yaml-01M4NVEN/
├── plan.md              # This file
├── research.md          # Phase 0 output (consolidated grounding)
├── data-model.md        # Phase 1 output (descriptor + provenance model)
├── quickstart.md        # Phase 1 output (how the pieces fit)
├── contracts/           # Phase 1 output (pack.yaml field contract + error codes)
├── tracers/             # design-decisions / approach / tooling-friction
└── tasks.md             # Phase 2 output (/spec-kitty.tasks)
```

### Source Code (repository root)

```
src/
├── kernel/
│   └── pack_tiers.py                      # single authority — gains the unified provenance spelling note (IC-07); doctrine comments updated
├── charter/
│   ├── offering/
│   │   ├── packs/
│   │   │   ├── pack_descriptor.py         # IC-01: + pack_level/requires_core/active_charter/pack_drg; pack_version level-conditional
│   │   │   ├── pack_validator.py          # IC-02/IC-03: PACK_LEVEL_MISMATCH/MISSING; branch-on-level; route through resolution seam
│   │   │   ├── pack_manifest.py           # (unchanged snapshot_sha256) — IC-06 clean-tree digest added here or in builtin_manifest.py
│   │   │   ├── builtin_manifest.py        # IC-06: clean-tree digest basis (enumerated/LF-normalized)
│   │   │   └── (new) pack_layout.py?      # IC-03: the (pack_root, descriptor) -> paths resolution seam (location TBD in tasks)
│   │   ├── base.py                        # IC-07: _provenance emitter "builtin" -> "built-in"
│   │   ├── agent_profiles/repository.py   # IC-07: _LAYER_RANK respell
│   │   └── activation/…                   # IC-07: context_json, progressive_disclosure, mission_type_profiles respell
│   ├── diagrams/                          # IC-09: pack-descriptor-model.{puml,svg} (drafted)
│   └── README.md                          # IC-09: diagram embed (drafted)
├── specify_cli/
│   ├── cli/commands/charter/pack_tooling.py  # IC-06: regenerate-graph --pack-root
│   ├── cli/commands/charter/pack_asset.py    # IC-07: asset list --json tier respell
│   ├── tool_surface/profiles/projection.py   # IC-07: source_layer respell
│   ├── skills/… , invocation/…               # IC-07: rank/order/routing respell (3-tier only)
│   └── upgrade/migrations/m_*_pack_level_backfill.py  # IC-04: new project-pack backfill migration
packs/
├── built-in/pack.yaml                     # IC-05: + pack_level: built-in
└── internal/pack.yaml                     # IC-05: NEW (pack_level: org, pointers, pinned id)
docs/
├── adr/4.x/2026-10-11-2-…md               # IC-09: folded in (Decision §2 aligned)
├── context/charter.md, governance.md      # IC-09: pack-tier prose
└── changelog/… , CHANGELOG.md             # IC-09
tests/
├── architectural/test_pack_manifest_no_author_edit.py       # IC-08 (FR-018)
├── architectural/test_pack_tier_token_single_authority.py   # IC-08 (FR-019)
├── architectural/test_pack_level_single_authority.py (NEW)  # IC-08 (FR-020)
├── charter/ , charter_offering/                             # IC-07 respell assertions
└── upgrade/                                                 # IC-04 migration tests
```

**Structure Decision**: single-project library+CLI, edits localized per the enforced import chain. The `.kittify/agent_profiles_manifest.json` dogfood file is updated in IC-07 (FR-017). The coord worktree (`.worktrees/…-01M4NVEN-coord/`) holds lifecycle surfaces only.

## Complexity Tracking

*No Charter Check violations — section intentionally empty.*

## Implementation Concern Map

> Concerns are NOT work packages. `/spec-kitty.tasks` translates these into WPs with lanes.

### IC-01 — Descriptor schema
- **Purpose**: Add the new `pack.yaml` fields so a pack can declare its level and layout.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-005
- **Affected surfaces**: `src/charter/offering/packs/pack_descriptor.py` (+ `retired_fields.py` context); `kernel.pack_tiers` (import `PackTier`)
- **Sequencing/depends-on**: none (foundational)
- **Risks**: `extra="forbid"` + `frozen=True` means every new field must be declared; `pack_version` conditional requiredness needs a `model_validator`; `active_charter`/`pack_drg` are strings validated as in-pack relative paths at validation time (IC-03), not at model time.

### IC-02 — Load-time level refusals
- **Purpose**: Refuse a mis-placed pack by name (`PACK_LEVEL_MISMATCH`) and warn on a missing field (`PACK_LEVEL_MISSING`).
- **Relevant requirements**: FR-006, FR-007
- **Affected surfaces**: `pack_validator.py` (`_validate_pack_descriptor` + the built-in and org load paths); the org-pack load path (`org_pack_loader`/`org_pack_config`) must gain a `pack.yaml` read; a single module-level constant gates the MISSING hard-refuse (default = warn).
- **Sequencing/depends-on**: IC-01
- **Risks**: "configured position" must be defined per tier (built-in root / `charter_packs.org.packs` entry / `.kittify/charter-packs`); the mismatch check needs that left-hand side or must skip (never silently pass a wrong level).

### IC-03 — Validate branch-on-level + layout resolution seam
- **Purpose**: `charter pack validate` branches on declared level; one seam resolves active-charter + DRG paths.
- **Relevant requirements**: FR-008, FR-009
- **Affected surfaces**: `pack_validator.validate_pack` (replace files-present branching with level branching); a single resolver `(pack_root, descriptor) -> (active_charter_path, drg_path)` with per-level convention fallback; existing filename lookups routed through it.
- **Sequencing/depends-on**: IC-01
- **Risks**: must not regress the current built-in/org/project validation behaviour for packs that omit the pointer fields (convention fallback must reproduce today's lookups).

### IC-04 — Project-pack backfill migration
- **Purpose**: Write `pack.yaml` (`pack_level: project`, minted `pack_id`) for existing project packs.
- **Relevant requirements**: FR-010
- **Affected surfaces**: new `src/specify_cli/upgrade/migrations/m_*_pack_level_backfill.py`; uses config-aware discovery; never `mkdir`; skips built-in/internal; never clobbers an authored `pack.yaml`.
- **Sequencing/depends-on**: IC-01
- **Risks**: migration idempotency; must leave a differing existing `pack_id` untouched; `tests/upgrade/` coverage.

### IC-05 — In-repo descriptors (built-in + internal)
- **Purpose**: Bring the repo's own packs into compliance.
- **Relevant requirements**: FR-011, FR-012
- **Affected surfaces**: `packs/built-in/pack.yaml` (+ `pack_level: built-in`); new `packs/internal/pack.yaml` (pinned `pack_id`, `active_charter: org-charter.yaml`, `pack_drg: drg/fragment.yaml`); a drift test pinning internal's `pack_id`.
- **Sequencing/depends-on**: IC-01; couples with IC-08 (the authored-field gate must accept the new built-in key set first/with this).
- **Risks**: editing `packs/**` trips the pack-manifest regen gate → run `spec-kitty charter pack regenerate-graph` after; internal is NOT sharded and has no manifest, so only built-in regen applies.

### IC-06 — Vendoring tooling (#6046)
- **Purpose**: `regenerate-graph --pack-root`, a reusable `requires_core` compatibility check, and a clean-tree drift digest.
- **Relevant requirements**: FR-013, FR-014, FR-015
- **Affected surfaces**: `pack_tooling.py` (plumb `--pack-root` through the `_built_in_pack_root()` seam for write + `--check`); a `requires_core` checker (consumes FR-002's field); a new clean-tree digest (enumerated-known-files, LF-normalized) beside `builtin_manifest.py`, leaving `snapshot_sha256` + its two callers byte-unchanged.
- **Sequencing/depends-on**: FR-002 (IC-01) for `requires_core`; digest + `--pack-root` independent.
- **Risks**: digest must be identical across `git archive` export / worktree / installed copy (NFR-003); NFR-004 pins the install-record path unchanged.

### IC-07 — Provenance unification (#5992)
- **Purpose**: Respell the 3-tier provenance/layer value `"builtin"` → `"built-in"`, unified on `kernel.pack_tiers`.
- **Relevant requirements**: FR-016, FR-017
- **Affected surfaces**: emitter `base.py:_provenance`; `_LAYER_RANK`, `_TIER_RANK`, `_LAYER_ORDER`, routing frozenset, `Tier` Literal; mappers (`skill_preparation`, `profiles_cmd`, `_charter_pack_collect`); `mission_type_profiles` default; serialized surfaces (`context_json`, `progressive_disclosure`, `projection`, `pack_asset`); `.kittify/agent_profiles_manifest.json` (dogfood). ~7 serialized-contract test files + ~30 in-memory test files.
- **Sequencing/depends-on**: coordinates with IC-08 (the tier-token gate carve-out must drop in lockstep with the respell, or the gate goes red).
- **Risks**: scope fence (C-002) — do NOT touch `skills/manifest.py`/`registry.py` `builtin|pack` origin nor `"builtin:"` prefix. Large test churn → isolate in its own lane. No consumer data migration (verified).

### IC-08 — Gates (authored-field, single-authority ×2)
- **Purpose**: Update the gate contracts that this change deliberately shifts, and add the new pack_level single-authority gate.
- **Relevant requirements**: FR-018, FR-019, FR-020
- **Affected surfaces**: `test_pack_manifest_no_author_edit.py` (field set += `pack_level`); `test_pack_tier_token_single_authority.py` + docstring + `kernel/pack_tiers.py` comments (extend to unified spelling, drop NFR-003 carve-out, keep empty allowlist); new `test_pack_level_single_authority.py` (derive-from-kernel, negative/self-mutation pin, empty allowlist).
- **Sequencing/depends-on**: FR-018 ↔ IC-05; FR-019 ↔ IC-07; FR-020 ↔ IC-01.
- **Risks**: the two gate changes must land atomically with their code (a red gate between commits is acceptable only within a lane, never at a WP boundary).

### IC-09 — ADR fold + docs + diagram
- **Purpose**: Fold the governing ADR, update prose, and ship the descriptor-model diagram.
- **Relevant requirements**: FR-021, FR-022, FR-023
- **Affected surfaces**: `docs/adr/4.x/2026-10-11-2-…md` (+ index/inventory entries, Decision §2 aligned to reuse-Literal); `docs/context/charter.md` + `governance.md`; `CHANGELOG.md` (+ `docs/changelog/`); `src/charter/diagrams/*` + `src/charter/README.md` (drafted — review + fold); close #6049.
- **Sequencing/depends-on**: none (docs); the ADR fold should reflect the final shipped design.
- **Risks**: docs-freshness / US-spelling / page-inventory + docs-retrieval-index regeneration gates (`inventory_lockfile --write`, `docs_index --write`); #6049's ADR carries index/inventory diffs to reconcile.

## Plan-point-cut adversarial squad — folded refinements (authoritative)

An architect (architect-alphonso) + planner (planner-priti) squad reviewed this plan. Their findings refine the IC map above and set the WP/lane carve-up for `/spec-kitty.tasks`. Where this section and the IC map differ, **this section wins**.

### WP → lane mapping (IC-08 dissolved; its 3 gate FRs co-locate with their code)

| WP | Lane | Concerns | Depends | Owns (no cross-lane file overlap) |
|----|------|----------|---------|-----------------------------------|
| **WP01** | A (root) | IC-01 + **FR-020** gate | — | `pack_descriptor.py`; NEW `tests/architectural/test_pack_level_single_authority.py` (+ `check_requires_core` predicate may live here). **Imports — never edits — `kernel/pack_tiers.py`.** |
| **WP02** | B | IC-02 **+** IC-03 (merged) | WP01 | `pack_validator.py`; NEW `charter/offering/packs/pack_layout.py` (the one seam); org-path `pack.yaml` read in `org_pack_loader.py`/`org_pack_config.py` |
| **WP03** | C | IC-04 migration | WP01 | NEW `specify_cli/upgrade/migrations/m_*_pack_level_backfill.py`; `tests/upgrade/` |
| **WP04** | D | IC-05 + **FR-018** gate | WP01 | `packs/built-in/pack.yaml`, NEW `packs/internal/pack.yaml`, `test_pack_manifest_no_author_edit.py`, internal `pack_id` drift test; **runs `regenerate-graph` (default root) + commits the regenerated built-in `pack-manifest.yaml`** |
| **WP05** | E | IC-06 tooling | WP01 (requires_core field) | `pack_tooling.py`, NEW clean-tree digest beside `builtin_manifest.py`, `requires_core` checker |
| **WP06** | F (ISOLATED) | IC-07 **+** **FR-019** gate | — (parallel from t0) | emitter `base.py`, `_LAYER_RANK`/`_TIER_RANK`/`_LAYER_ORDER`/routing frozenset/`Tier` Literal/mappers/serialized surfaces, `kernel/pack_tiers.py` (spelling + docstring), `.kittify/agent_profiles_manifest.json`, `test_pack_tier_token_single_authority.py`, ~7 serialized-contract + ~30 in-memory test files |
| **WP07** | G | IC-09 ADR + docs + diagram | reflects final design (fold **last**) | `docs/adr/4.x/2026-10-11-2-…md` (+ index/inventory), `docs/context/{charter,governance}.md`, `CHANGELOG.md`, `src/charter/README.md`+`diagrams/*` |

**Critical path**: WP01 → WP02 (deepest). **WP06 is the second long pole — independent of WP01, start at t0.** After WP01, WP02/03/04/05 run in parallel; WP06/WP07 parallel from t0. Max concurrency ≈ 4–6 by load.

### Lockstep pairs (atomic within a lane; never red at a WP boundary)
- **LS-1** IC-07 respell ↔ FR-019 tier-token gate carve-out drop → **both in WP06**.
- **LS-2** built-in `pack.yaml` += `pack_level` ↔ FR-018 authored-field key set → **both in WP04**.
- **LS-3** IC-01 `pack_level` field ↔ FR-020 new empty-allowlist gate (non-vacuous same mission, DIRECTIVE_043) → **both in WP01**.
- **LS-4** `packs/**` edit ↔ pack-manifest regen → **WP04 runs `spec-kitty charter pack regenerate-graph`** and commits the result (built-in only; internal is unsharded/no manifest).

### Architect design corrections (bind the tasks phase)
- **A — Resolution seam home + return contract.** The seam lives in `charter/offering/packs/pack_layout.py` (NOT kernel — it takes a `PackDescriptor`); its convention-fallback **delegates to the existing `kernel.charter_pack_paths` constants** (`DRG_FRAGMENT`, `ORG_CHARTER_FILENAME`, `PROJECT_GRAPH_FILENAME`, helpers `pack_drg_fragment`/`pack_org_charter`). Its `drg_path` return is **"a path `charter/offering/drg/loader.py::load_graph_or_dir` accepts" (file OR directory)** — so built-in's sharded root fits the same seam with no separate branch. Contract/data-model must state file-vs-root explicitly.
- **B — `PACK_LEVEL_MISMATCH` configured position (real gap).** `validate_pack(pack_dir)` has **no position context**; mismatch is not computable on a bare path. Add a pure `check_pack_level(descriptor, expected_level: PackTier | None) -> ValidationIssue | None`; position-aware callers pass `expected_level` (built-in root / `charter_packs.org.packs[]` entry / `project_pack_root`); on a bare path with no context, **skip mismatch (fail-closed: never silently pass) but still run MISSING + schema**. This is WP02's riskiest sub-task (org-path read touches `org_pack_config.OrgPackConfig`, 57 callers) — bound it with its own regression anchor.
- **C — Clean-tree digest must be level-aware.** `builtin_manifest`'s `enumerate_constituents` is built-in-only (`has_built_in_content_dir`, nine kinds) and **misses `org-charter.yaml` + `drg/fragment.yaml`**; `snapshot_sha256` is noisy rglob. The digest enumerates a **declared, level-aware file set**: `RECOGNISED_ARTIFACT_DIRS` + the level's layout files **from the FR-009 seam** + `pack.yaml`, LF-normalized via `_lf_normalized`. The seam becomes the single enumerator of "where a level's files live."
- **D — IC-07 + FR-019 is ONE commit, derive-don't-allowlist.** Respelling provenance to `"built-in"` makes **every** sibling display (`_LAYER_RANK`, `_LAYER_ORDER`, routing frozenset, `Tier` Literal) a full-tier restatement → the MAIN gate test reds, not just the carve-out test. So WP06's single commit must (1) respell emitter + every sibling, (2) **convert each respelled display to DERIVE from `kernel.pack_tiers`** (keep the allowlist empty — do NOT allowlist), (3) update/remove the carve-out test, (4) rewrite the NFR-003 Scope-note in `pack_tiers.py` and the gate docstring.

### New contradictions to retire explicitly
1. **NFR-003 carve-out language** in `pack_tiers.py:13-20`, the gate docstring, and (folded) the ADR currently assert the provenance fold has NOT happened. This mission IS that fold → retire that language explicitly and traceably (WP06 + WP07). The fold strengthens single-authority (two vocabularies → one).
2. **Cross-version persisted-value note** → record in the ADR consequences: the fold changes the serialized provenance spelling; verified safe for the current CLI (no read-back compares to `"builtin"`; regenerated JSON + dogfood manifest self-heal); the one theoretical edge is an *older* CLI reading a new-spelling artifact post-upgrade.
3. **`pack_version` double-meaning** → `packs/built-in/pack.yaml` carries `pack_version`; the generated `pack-manifest.yaml` still omits it. Do not conflate the two in a fixture (WP04).

### WP06 scope-fence enumeration (prevent a bad respell — top hazard)
The WP06 brief MUST carry an explicit in/out symbol list before any edit:
- **IN (3-tier provenance/layer)**: `base.py::_provenance`/`get_provenance`, `agent_profiles/repository.py::_LAYER_RANK`, `pack_skills/repository.py::_TIER_RANK` (3-tier — in scope despite sitting beside the fenced skill-origin vocab), `_charter_pack_health.py::_LAYER_ORDER`, `invocation/registry.py` routing frozenset, `pack_skills/validation.py::Tier`, the `skill_preparation`/`profiles_cmd`/`_charter_pack_collect` mappers, `mission_type_profiles` provenance default, serialized `context_json`/`progressive_disclosure`/`projection`/`pack_asset`.
- **OUT (C-002 fence)**: `skills/manifest.py`/`registry.py` `builtin|pack` skill-origin; `pack_skills/models.py` `"builtin:"` command-target prefix; `retrospective/reader.py::_provenance` (a different, non-artifact-layer provenance).
