# Implementation Plan: One org-pack chain authority

**Branch**: `kitty/org-pack-chain-authority-stack` (stacked on PR #6005) | **Date**: 2026-10-10 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/org-pack-chain-authority-01M4JXF5/spec.md`

## Summary

Make a single `resolve_pack_chain()` the only authority that produces the
ordered, existing organization-pack chain (last-declared-wins), with a strict
posture that fails closed on a declared-but-missing pack (#4984 seam) and a
lenient posture that degrades silently. Migrate every current chain-deriving
caller onto it, fix the surfaces that still read pack #1 only (`charter list
--all`, the dead `ProjectContext.org_root`, the `action_governance_bundle`
legacy param), retire the `_activate_cascade_target` retry loop by widening
`ActiveCharterManager` with an `org_root_chain` parameter, and lock the
single-authority invariant with an empty-allowlist architectural gate. Add a
#5956 **loader seam** (a `RequirementKind`/`RequirementKindDeclaration` model and
`load_requirement_kinds()` that resolves `requirement-kinds.yaml` through the same
chain, built-in → org last-wins → project, fail-closed) — not the #5956 gate
handlers, glossary, or grammar.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: Pydantic v2 (models, `extra="forbid"`), ruamel.yaml (existing YAML reads), Typer (CLI). No new third-party dependency is added or upgraded — the Supply-Chain Security section is therefore N/A for this mission.
**Storage**: Filesystem — `.kittify/config.yaml` (`charter_packs.org.packs`), org/project pack trees, and a new `requirement-kinds.yaml` declaration file per mission type per tier.
**Testing**: pytest; ATDD/red-first per ADR 2026-07-17-1; architectural AST-census gate mirroring `tests/architectural/test_remote_contact_owner.py`; targeted module tests + the specific owning-subsystem test dirs (`tests/charter/`, `tests/charter_offering/`, `tests/specify_cli/cli/commands/charter/`). CI owns full suites.
**Target Platform**: Linux/macOS dev + CI (the spec-kitty CLI).
**Project Type**: single (library + CLI); layering `kernel <- charter <- {glossary, runtime, mission_runtime} <- specify_cli`.
**Performance Goals**: No regression on the resolution hot path (`resolve_org_dirs`, template/mission/FSM resolution) — behavior byte-identical (NFR-004); the authority adds one registry read already performed today.
**Constraints**: `resolve_layer_roots` `dict[str, Path]` contract unchanged (NFR-001); `_org_scan_dirs` flat-wins precedence unchanged (NFR-005); empty allowlist, no ratchet (NFR-002); ruff+mypy clean, complexity ≤15 (NFR-003).
**Scale/Scope**: ~18-20 modules touched (the chain-deriving callers), concentrated in `src/charter/activation/` and `src/charter/offering/`, plus three `src/specify_cli/cli/commands/charter/` surfaces and one new loader module. Stacked on #6005 (6 commits).

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** (Governing Principle): ✅ the mission's reason for being — one `resolve_pack_chain()`, no parallel authority; the lower DRG readers survive only as module-private primitives (C-004).
- **Empty-allowlist invariant** (Standing Order #5 / ADR 2026-09-30-1): ✅ the architectural gate ships with zero allowlist entries and no shrink-only ratchet (NFR-002).
- **Architectural alignment / layering**: ✅ authority lives in the `charter` tier; chain handed down as `list[Path]` data (C-001); enforced by `tests/architectural/test_layer_rules.py`.
- **ATDD-first / red-first** (Standing Order): ✅ each FR lands an issue-pinned regression repro that is red through the production entry point before the fix.
- **Reconcile change-scope tensions**: the empty-allowlist gate forces a wide caller migration (~18-20 modules). Justified: the issue explicitly asks for "only that authority computes the chain"; a narrower gate would leave the parallel-authority defect standing. Not a violation — recorded in Complexity Tracking.
- **Terminology**: no `feature*`/`ceremony`/`status-writing`; run `tests/architectural/test_no_legacy_terminology.py` before push (prose touched).
- No charter conflict. No hosted/Team-Kitty surface touched (C-003).

## Project Structure

### Documentation (this mission)

```
kitty-specs/org-pack-chain-authority-01M4JXF5/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (entities + requirement-kinds.yaml schema)
├── quickstart.md        # Phase 1 output
├── tracers/             # 3 tracer files (seeded here)
└── tasks.md             # Phase 2 (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root)

```
src/charter/activation/
├── layer_roots.py                 # AUTHORITY HOME: new resolve_pack_chain(); absorb resolve_org_root_chain
├── pack_manager.py                # widen ActiveCharterManager.{activate,list_available,list_available_detailed,_scan_layer_dirs} with org_root_chain
├── effective_set.py               # migrate _scanned_ids / _declared_org_roots / _readable_roots / _fallback_ids onto authority
├── preset_application.py          # migrate _Roots.of / _available_mission_types onto authority
├── invocation_context.py          # remove dead ProjectContext.org_root
├── action_governance_bundle.py    # drop legacy org_root param (lenient chain already threaded)
├── manifest_loader.py             # NEW load_requirement_kinds() beside load_manifest()
└── org_expected_artifacts.py      # sibling pattern for NEW resolve_org_requirement_kinds()

src/charter/offering/drg/org_pack_config.py   # resolve_org_roots/existing/declared stay as MODULE-PRIVATE primitives (authority-only callers)
src/charter/offering/missions/
├── requirement_kinds.py           # NEW RequirementKind / RequirementKindDeclaration (frozen, extra="forbid")
└── expected_artifact_manifest.py  # precedent mirrored

src/specify_cli/cli/commands/charter/
├── list_cmd.py                    # full-chain template + availability scan (FR-003)
├── activate.py                    # retire _activate_cascade_target; single widened scan
├── deactivate.py                  # re-point onto authority
└── _cascade_shared.py             # re-point onto authority

tests/architectural/test_org_pack_chain_single_authority.py   # NEW empty-allowlist gate
tests/charter/, tests/charter_offering/, tests/specify_cli/cli/commands/charter/   # targeted + regression repros
```

**Structure Decision**: Single library+CLI project. The authority lives in `src/charter/activation/layer_roots.py`; the three DRG registry readers stay in `src/charter/offering/drg/org_pack_config.py` but become callable only from the authority module and their own module. The new loader seam adds `src/charter/offering/missions/requirement_kinds.py` + `load_requirement_kinds` in `manifest_loader.py`.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Wide caller migration (~18-20 modules) in one mission | The empty-allowlist gate (FR-006) goes red on introduction unless every chain-deriving caller already routes through the authority | A narrower gate (forbid only `[0]` reads) would leave two spellings of "get the chain" and the parallel-authority defect the issue exists to kill; the charter's single-canonical-authority principle requires the full migration |
| Loader seam adds a new file format (`requirement-kinds.yaml`) not consumed yet | Operator ruling: include the #5956 loader seam so #5956 builds on a settled chain authority | Deferring it would re-open the authority's API when #5956 lands; the seam is model + loader only (no handlers), so the added surface is bounded |

## Implementation Concern Map

> Concerns are NOT work packages. `/spec-kitty.tasks` translates these into WPs.

### IC-01 — Pack chain authority

- **Purpose**: Introduce `resolve_pack_chain(repo_root, *, strict)` as the sole producer of the ordered, existing org-pack chain (last-declared-wins), with strict (fail-closed, names the unfetched pack + `spec-kitty charter fetch`) and lenient (existing-filtered) postures. Absorb `resolve_org_root_chain`.
- **Relevant requirements**: FR-001, FR-007; NFR-002 (home for the invariant).
- **Affected surfaces**: `src/charter/activation/layer_roots.py` (home), `src/charter/offering/drg/org_pack_config.py` (strict = today's `require_declared_org_roots` logic; lenient = `resolve_existing_org_roots`).
- **Sequencing/depends-on**: none (foundation).
- **Risks**: must not change `resolve_layer_roots`'s `dict[str,Path]` (NFR-001); strict posture must not fire when zero packs are declared (edge case).

### IC-02 — Migrate chain-deriving callers onto the authority (incl. lenient re-point)

- **Purpose**: Route every chain-deriving site through `resolve_pack_chain()`, including re-implementing the lenient surfaces (`resolve_org_dirs`, `effective_set._readable_roots`/`_fallback_ids`) over `resolve_pack_chain(strict=False)` so no module calls a primitive directly. Re-point (not re-fix) the already-correct `context.py`/`--include` reader.
- **Relevant requirements**: FR-002, FR-008; NFR-004 (byte-identical lenient behavior), NFR-005 (`_org_scan_dirs` flat-wins preserved).
- **Affected surfaces**: ALL chain-deriving callers in the charter surfaces (`src/charter/**`, `src/specify_cli/cli/commands/charter/**`): `effective_set`, `preset_application`, `org_charter`, `active_charter_service_builder`, `_drg_helpers`, `language_vocabulary`, `profile_resolution`, `project_registration`, `skill_preparation`, `offering/resolver`, `manifest_loader`'s `load_manifest` path, and the `cli/commands/charter/*` consumers (`deactivate`, `_resynthesis_preflight`, `interview`, `context` re-point, `pack_asset`). `org_pack_config.resolve_org_dirs` re-points internally (WP01). `_cascade_shared` / `activation/context` are docstring-only. Split across WP02 (activation core), WP07 (remaining activation/offering), WP08 (CLI charter), WP05 (manifest_loader).
- **Sequencing/depends-on**: IC-01.
- **Scope**: charter surfaces only this mission; ~12 non-charter callers are a named follow-up (operator ruling — see spec Out of Scope).
- **Risks**: lenient re-point must preserve the per-dropped-root WARNING (NFR-004); `_org_scan_dirs` precedence must stay (NFR-005); per-surface posture (strict vs lenient) matches today's behavior unless the surface is a governance decision.

### IC-03 — Fix the pack-1-only readers

- **Purpose**: `charter list --all` lists org artifacts/templates from the full chain (FR-003); remove the dead `ProjectContext.org_root` field; drop the `action_governance_bundle` legacy `org_root` param (lenient resolution preserved).
- **Relevant requirements**: FR-003, FR-005.
- **Affected surfaces**: `list_cmd.py` (:88 templates, :197/:245 availability — mirror `effective_set._scanned_ids` per-root scan), `invocation_context.py` (:82/:106), `action_governance_bundle.py` (:211-215). Updates `TestListAllLayersBackCompat` (SUPERSEDE the pack-2-hidden assertion; KEEP the other two).
- **Sequencing/depends-on**: IC-01; coordinates with IC-02.
- **Risks**: must not widen `resolve_layer_roots` dict (NFR-001); the `TestListAllLayersBackCompat` keep/supersede split must be applied exactly (spec FR-003).

### IC-04 — Retire the retry loop (widen ActiveCharterManager)

- **Purpose**: Remove `_activate_cascade_target`; widen `ActiveCharterManager.activate`/`list_available`/`list_available_detailed`/`_scan_layer_dirs` with `org_root_chain: list[Path] | None`, emitting one ORG pair per chain root last-declared-first, falling back to the single `layer_roots["org"]` slot when None.
- **Relevant requirements**: FR-004.
- **Affected surfaces**: `pack_manager.py` (:661/:685/:869/:900/:1001), `activate.py` (:236-303 removed, :1038 collapsed). Pins: `tests/charter/test_pack_manager*.py`, `test_mission_type_path_layout_ssot.py`.
- **Sequencing/depends-on**: IC-01.
- **Risks**: reproduce `_org_scan_dirs` last-declared-first precedence; verify no test calls `activate(layer_roots=...)` positionally.

### IC-05 — Empty-allowlist architectural gate

- **Purpose**: An AST-census test (mirroring `test_remote_contact_owner.py`) whose **scope is `src/charter/**` + `src/specify_cli/cli/commands/charter/**`** (this mission; follow-up widens tree-wide), forbidding any in-scope module outside the authority module and the primitives' own module from calling a chain primitive or iterating `load_pack_registry().packs` to assemble roots. Empty allowlist (no ratchet); scope is the bound, not an allowlist. File-count floor + planted-violation + owner-bypass controls.
- **Relevant requirements**: FR-006; NFR-002.
- **Affected surfaces**: `tests/architectural/test_org_pack_chain_single_authority.py` (new).
- **Sequencing/depends-on**: every migration WP (lands last — goes red if any in-scope migration is incomplete).
- **Risks**: discriminator must be module-ownership, not symbol-name blanket (else false positives on legitimate single-root `resolve_layer_roots`); non-vacuity controls mandatory.

### IC-06 — Requirement-kinds loader seam (#5956)

- **Purpose**: `RequirementKind`/`RequirementKindDeclaration` frozen models (`extra="forbid"`) + `load_requirement_kinds(mission_type, repo_root)` mirroring `load_manifest`: resolve `requirement-kinds.yaml` through built-in → org full-chain (last-wins, via strict authority) → project tier (`.kittify/doctrine/missions/<type>/requirement-kinds.yaml`, project wins), whole-file override, fail-closed on invalid/missing.
- **Relevant requirements**: FR-009, FR-010, FR-011; SC-004.
- **Affected surfaces**: NEW `requirement_kinds.py`; `manifest_loader.py` (`load_requirement_kinds`); NEW `resolve_org_requirement_kinds` sibling of `resolve_org_expected_artifacts`. Mirrors `ManifestSchemaError`/`MalformedManifestError`.
- **Sequencing/depends-on**: IC-01 (uses the strict authority for the org chain — a documented divergence from `load_manifest`'s lenient resolution; adds the project tier `load_manifest` lacks).
- **Risks**: the two divergences from the `load_manifest` precedent (project tier; strict org chain) must be deliberate and documented, not accidental.
