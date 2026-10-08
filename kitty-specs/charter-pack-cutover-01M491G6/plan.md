# Implementation Plan: Charter offering, activation presets and the doctrine-to-charter cutover

**Branch**: `issue-3732-charter-pack-rename` | **Date**: 2026-10-06 | **Spec**: [spec.md](spec.md)
**Input**: Mission specification from `kitty-specs/charter-pack-cutover-01M491G6/spec.md`

**Note**: This template is filled in by the `/spec-kitty.plan` command. See `packs/built-in/missions/mission-steps/software-dev/plan/prompt.md` for the execution workflow.

The planner will not begin until all planning questions have been answered—capture those answers in this document before progressing to later phases.

## Summary

Cut the retired "doctrine" tier over to the charter vocabulary in one release, with no aliases or shims (ADR 2026-10-06-1 and its 2026-10-06 amendment). Activation presets become pack data applied by `charter activate --preset`; the `default` preset lists nothing so it cannot drift (#5323), and promotion of absent keys seeds from the effective set (#4400). The project layer moves to `.kittify/charter-packs/` on both the read and the write side. One upgrade migration, ordered before every other pending migration, rewrites persisted project state once; after it, legacy state fails at the CLI root with an error naming `spec-kitty upgrade`. The `specify_cli.doctrine` package is split by meaning into `charter.offering.packs`, `charter.activation` and `specify_cli.charter_packs`. WP01 writes every FR's acceptance test first (C-006); every later work package flips its own strict `xfail`s.

Research: [research.md](research.md) (index), [research/runtime-seams.md](research/runtime-seams.md), [research/package-split-and-paths.md](research/package-split-and-paths.md), [research/default-yaml-snapshots.md](research/default-yaml-snapshots.md), post-spec squad reports in [research/](research/).

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, ruamel.yaml, pydantic, pytest, pytestarch (architectural gates); no new dependencies
**Storage**: files: `.kittify/config.yaml`, `.kittify/charter/charter.yaml`, `.kittify/charter-packs/` (project layer), pack directories (`pack.yaml`, `org-charter.yaml`, `presets/*.yaml`)
**Testing**: pytest; acceptance tests first as strict xfail (C-006); CLI-level tests via CliRunner; architectural gates in `tests/architectural/`; golden NFR-001 sets frozen at the mission base
**Target Platform**: Linux, macOS, Windows (CLI)
**Project Type**: single (Python CLI + libraries under `src/`)
**Performance Goals**: `charter activate --preset` and `charter pack list` ≤ 1.5× `charter list` (NFR-003)
**Constraints**: no aliases or shims (C-001); historical records immutable (C-002); layering kernel <- charter <- specify_cli (C-007); ordering C-008
**Scale/Scope**: ~19 work packages; FR-010 touches ~419 src files; migration covers the FR-012 inventory

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan complies |
|---|---|
| Single canonical authority; canonical sources | One kernel path module (FR-016), one preset loader in `charter` (FR-004), one effective-set seam (FR-015), one migration (FR-012), one detection predicate shared by the CLI root gate and the migration's `detect()`. |
| Architectural alignment / layering | C-007: `kernel` path constants; preset discovery, effective-set seam, layer roots, pack model and org charter composition in `charter`; adapters stay in `specify_cli`. The offering→activation import ban (`test_charter_offering_does_not_import_activation.py`) is honoured by the prep moves in research/package-split-and-paths.md §A. |
| ATDD-first (C-011) and C-006 | WP01 commits acceptance tests as strict `xfail` (red on base); each WP's first commit removes its own `xfail` markers (red), the WP turns them green. Reviewer checks red-on-base → green-on-final. |
| Burn-down policy | Every gate touched closes with an empty allowlist (NFR-002); the `specify_cli/doctrine` boundary exemption is deleted, not moved; no new baseline entry. Pure-shim files shrink (the CR-01/CR-02/CR-03/CR-04/CR-07 shims are deleted). |
| User customization preservation | Customised activation lists are never rewritten (reported); the migration carries uncommitted edits over and refuses on colliding paths; user-chosen path values are never rewritten. |
| Pack tiers | `packs/built-in` gains only the consumer presets; `packs/internal` prose is updated in place; `charter pack regenerate-graph` after every pack edit. |
| Terminology canon | Mission, never "feature"; the FR-018 gate enforces the retired tokens; `test_no_legacy_terminology.py` before every push. |
| No heavy suites in mission | Each WP runs `make test-fast`, its touched-module tests, the owning subsystem directories (`tests/charter/`, `tests/doctrine/` when `src/charter/offering/**` moves) and the specific architectural gate files it implicates; never bare `tests/architectural/` or `make test-full`. |
| Git workflow | Topic branch `issue-3732-charter-pack-rename`; one draft PR to `main` (OD-10); the operator merges. |

No violations; Complexity Tracking is empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/charter-pack-cutover-01M491G6/
├── spec.md
├── plan.md                 # this file
├── research.md             # decision index (Phase 0)
├── research/               # squad reports and topic research
├── data-model.md           # preset, active charter, migration inventory (Phase 1)
├── contracts/              # CLI, preset schema, migration and error contracts (Phase 1)
├── quickstart.md           # operator and pack-author walkthrough (Phase 1)
├── occurrence_map.yaml     # bulk-edit classification (8 categories + moves)
└── tasks.md                # /spec-kitty.tasks
```

### Source Code (repository root)

```
src/kernel/
└── charter_pack_paths.py           # NEW (replaces doctrine_root.py): project pack root + pack-relative paths
src/charter/
├── offering/packs/                 # NEW: pack model + tooling (from specify_cli/doctrine), preset loader
├── activation/
│   ├── org_charter.py              # MOVED (+ org_charter_loader, config folded in)
│   ├── layer_roots.py              # MOVED from specify_cli/cli/commands/charter/_layer_roots.py
│   ├── effective_set.py            # NEW: public effective-set seam (FR-015)
│   └── packs/                      # DELETED (default.yaml, minimal.yaml, default_pack.py users repointed)
├── packs.py                        # NEW facade for specify_cli consumers (charter.packs)
└── drg.py                          # facade gains CORE_KIND_PLURALS, resolve_relative_path_within_root
src/specify_cli/
├── charter_packs/                  # NEW: sources/, snapshot.py, template_render/ (from doctrine/)
├── doctrine/                       # DELETED
├── charter_pack_registry.py        # DELETED
├── cli/commands/charter/           # activate --preset, pack {list,path,validate,assemble,regenerate-graph,asset}, consistency-check
├── cli/commands/doctrine.py        # DELETED (handlers moved under charter/)
├── upgrade/migrations/m_*_charter_pack_cutover.py  # NEW run-first migration (+ frozen snapshot data)
└── skills/retired.py               # removed skill names added
packs/built-in/presets/{default,minimal}.yaml       # NEW pack data
tests/
├── acceptance/charter_pack_cutover/  # WP01 acceptance suite (strict xfail per FR)
└── architectural/                    # FR-016 path gate, FR-018 vocabulary gate, updated census/boundary gates
```

**Structure Decision**: single Python project; the layout above is the delta. The tests/doctrine/ directory is renamed in its own late work package (mechanical; CLAUDE.md and pyproject references follow).

## Complexity Tracking

None.

## Key design decisions

Each is detailed, with evidence and rejected alternatives, in [research.md](research.md).

1. **Run-first migration**: a `runs_first` flag on `BaseMigration`, applied in `MigrationRegistry.get_applicable`; `get_all()` stays in version order. `detect()` checks content, not the version stamp.
2. **Older migrations neutralised** (detect false, recorded as skipped): `m_3_2_0rc35_default_charter_pack`, `m_3_2_x_normalize_activation_absence` (it writes `[]` = nothing activated for absent keys, contradicting the live absent-means-all contract and undoing the stale-list reset), `m_2_1_2_fix_glossary_context_skill`; module-level imports of deleted modules removed from `m_unify_charter_activation` and rc35; `m_3_1_1_charter_rename` stops recreating a retired skill directory; the finalize migration drops its call to the deleted compat helper.
3. **Detection seam**: one predicate in `_run_startup_project_gates` (`specify_cli/__init__.py`) — two `stat`s and a prefiltered read of `config.yaml` (never the large `charter.yaml`); exempt `upgrade`, `init`, `--version`, `--help`; checks the current checkout as well as the project root so a stale lane worktree is caught. `load_governance_config` fails closed on a legacy `governance.doctrine` key instead of silently dropping it.
4. **Preset application**: replace semantics over the governed keys, union with org `required_<kind>`, refuse without `--force` when a governed key would change, one atomic write via `resolve_activation_write_target`.
5. **Stale-list predicate**: per key, order-insensitive, id-normalised equality against frozen snapshots of every released `default.yaml` (original and post-retirement-rewrite forms), embedded as migration-private data.
6. **Package split**: prep moves first (hash helpers to offering, `org_extends` to `offering/packs/extends.py`, OrgCharterPolicy steps behind hooks, pure manifest writer out of `snapshot`), leaves before roots, atomic delete with roster/census updates last.
7. **Skill retirement**: user-global roots via `RETIRED_CANONICAL_SKILL_NAMES`; project roots via the upgrade finalizer plus a hash-matched removal step in the cutover migration for unmanifested copies; edited copies are kept and reported.
8. **Worktrees**: upgrade skips worktrees (#5457); the runbook tells lanes to merge the upgraded target, never rebase (a rebase loses the approval stamp).

## Implementation Concern Map

> Implementation concerns are not work packages. `/spec-kitty.tasks` maps them to WPs; the ordering edges below are C-008 plus research findings.

### IC-01 — Acceptance suite and golden "before" sets

- **Purpose**: turn every FR and measurable NFR into tests before implementation (C-006), and freeze NFR-001's "before" sets while the shims still exist.
- **Relevant requirements**: all FRs; NFR-001..004; SC-001..005
- **Affected surfaces**: `tests/acceptance/charter_pack_cutover/`, legacy fixture projects, golden JSON + generator + base SHA
- **Sequencing/depends-on**: none (first)
- **Risks**: golden sets must be generated with the pre-cutover code; each test names the IC/WP that turns it green; strict xfail so an accidental pass is caught.

### IC-02 — Kernel pack paths and write-side cutover

- **Purpose**: one kernel module for the project pack root and pack-relative paths; every reader and writer uses it.
- **Relevant requirements**: FR-016
- **Affected surfaces**: `kernel/doctrine_root.py` → `kernel/charter_pack_paths.py`; 56 path sites in 50 files (12 write); `state/contract.py`; `.gitignore`; `ci-router.yml` path filter; new FR-016 AST gate
- **Sequencing/depends-on**: IC-01
- **Risks**: the old root stays readable only through the migration until IC-06; staging subtree and org nested layout settled per research §B.

### IC-03 — Effective-set seam and fail-closed promotion

- **Purpose**: one public seam for "what is effective for an absent key"; four callers use it; promotion never writes a narrower list.
- **Relevant requirements**: FR-015
- **Affected surfaces**: `charter/activation/effective_set.py`, `layer_roots.py` move, `promote_activations`, interview, org-charter union, `m_unify_charter_activation`, `_resynthesis_preflight`; delete `merge_defaults` / `_load_default_pack`
- **Sequencing/depends-on**: IC-01
- **Risks**: two-org-pack chains and id≠stem artifacts (#4399); directives must be covered.

### IC-04 — Presets as pack data, preset format and activation

- **Purpose**: built-in `default`/`minimal` presets in the pack, a documented schema, charter-side discovery, `charter activate --preset`, `charter pack list/path`, init/generate/upgrade provisioning from the `default` preset.
- **Relevant requirements**: FR-001..FR-004, FR-019
- **Affected surfaces**: `packs/built-in/presets/`, preset schema in `src/charter/offering/schemas/`, `charter/offering/packs/presets.py`, `cli/commands/charter/activate.py`, `pack.py`, `provisioning/default_charter.py`, `compiler.provision_mission_type_activations`, pack manifest hashing, validator
- **Sequencing/depends-on**: IC-03
- **Risks**: replace semantics is a new write path (deletes keys); `minimal` content fix changes behaviour for projects that applied it (reported, not rewritten).

### IC-05 — Cutover upgrade migration

- **Purpose**: rewrite persisted project state once, before every other pending migration.
- **Relevant requirements**: FR-012, NFR-001, NFR-004
- **Affected surfaces**: new migration + frozen snapshot data, `runs_first` in registry, neutralised older migrations, `.gitignore`/synthesis manifest/provenance/skills-manifest rewrites, installed-skill removal, tracker ownership key, upgrade summary
- **Sequencing/depends-on**: IC-02, IC-04 (preset meaning), snapshot research
- **Risks**: highest-risk concern; pre-rc35 one-shot upgrade path; idempotence over the whole `spec-kitty upgrade`; Windows move.

### IC-06 — Remove the preset registry and the read-side shims

- **Purpose**: delete `charter_pack_registry`, `src/charter/activation/packs/`, `default_pack`, `charter pack apply`, `accompanies_doctrine_pack`, every legacy key/path fallback and compat warning; add the CLI-root detection seam and fail-closed governance loading.
- **Relevant requirements**: FR-005, FR-011
- **Affected surfaces**: registry, descriptor (`extra="forbid"` → explicit rejection message naming the field), `org_pack_config.py`, `sync.py`, `kernel` fallback, tracker CR-03, `_run_startup_project_gates`
- **Sequencing/depends-on**: IC-05
- **Risks**: `PackContext.from_config` must stay total; tests of the deleted shims are deleted, not adapted.

### IC-07 — CLI surface: charter homes and removal of the doctrine group

- **Purpose**: every `doctrine` leaf has its `charter` home; `doctor doctrine` → `doctor charter-packs`; consistency-check moves; the group is deleted.
- **Relevant requirements**: FR-006, FR-007
- **Affected surfaces**: `cli/commands/doctrine.py` (deleted), `charter/_app.py`, `_doctrine_*` command modules, `doctor.py`, `packs.yml`, `Makefile`, `builtin_manifest.py` `generated_by` (regenerate), AGENTS.md/CLAUDE.md, `packs/internal/**`, completion manifest, `#4836` guidance gate rewritten as a removed-command gate
- **Sequencing/depends-on**: IC-01; deletion after IC-04 (pack commands) 
- **Risks**: CI workflow must change in the same commit as the command; old spellings must hit Typer's unknown-command path (exit 2), not a hidden alias.

### IC-08 — Package split of specify_cli.doctrine

- **Purpose**: move code to where it belongs (OD-9) and delete the boundary exemption.
- **Relevant requirements**: FR-010 (part)
- **Affected surfaces**: research/package-split-and-paths.md §A (7-step order), `charter.packs` facade, census/boundary/roster/pyproject entries
- **Sequencing/depends-on**: IC-03 (layer roots), IC-06 (default_pack gone from org_charter)
- **Risks**: offering→activation import ban; ruff format-exclude entries drop and files get formatted.

### IC-09 — Identifier and prose rename

- **Purpose**: rename the retired-tier sense per the occurrence map across src, packs, docs and tests; three active-charter/preset/pack names (FR-009); `doctrine_pack_id` → `charter_pack_id`.
- **Relevant requirements**: FR-009, FR-010
- **Affected surfaces**: R1 offering/facades/kernel (~21 files), R2 activation (~42), R3 specify_cli commands and neighbours (~45), R4 migrations/synthesizer/gates (~15), docs and packs prose, golden `mission_create_refusals.json`, `ERROR_CODES.md`, then the `tests/doctrine/` directory
- **Sequencing/depends-on**: IC-08
- **Risks**: content-sense "doctrine" must survive (manual_review on prose); public facade exports renamed without aliases.

### IC-10 — Skills

- **Purpose**: `spk-charter-*` / `spk-practice-*`, fold the five backing skills, retire removed names everywhere, regenerate derived files.
- **Relevant requirements**: FR-008
- **Affected surfaces**: `src/charter/offering/skills/`, `skills/retired.py`, references in prompts/skills/docs, completion manifest, `docs/api/skills/*`, regen fixtures
- **Sequencing/depends-on**: IC-01; before IC-11
- **Risks**: SOURCE templates only; generated agent copies are git-ignored here.

### IC-11 — Glossary, messaging, reachability pins and the vocabulary gate

- **Purpose**: definitions, changelog Before/After, runbook, historical banners on superseded runbooks, reachability pins, and the FR-018 gate that keeps it all from regressing.
- **Relevant requirements**: FR-013, FR-014, FR-017, FR-018, NFR-002
- **Affected surfaces**: `docs/context/charter.md`, CHANGELOG Unreleased, `docs/migrations/charter-pack-cutover.md`, `test_reachability.py`, new vocabulary gate
- **Sequencing/depends-on**: all other concerns (the gate closes last)
- **Risks**: gate must scan ≥ the base-recorded floor and self-test every token.
