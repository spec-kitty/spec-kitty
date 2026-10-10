# Implementation Plan: Charter kind/tier vocabulary cutover closeout

**Branch**: `feat/charter-kind-tier-vocab-closeout` | **Date**: 2026-10-09 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/charter-kind-tier-vocab-closeout-01M4H5RF/spec.md`

## Summary

Finish the single-authority kind/tier vocabulary left by the merged doctrine→charter cutover and clean its inert residue. Five converging strands: (1) fix the facade re-export gate's blind spot for non-class values so a drifted tuple/frozenset cannot cross a facade unseen (#5836 — the enabler); (2) teach the kind-vocabulary gate the five mirror shapes it misses and migrate every live site to derive from `ArtifactKind` (#5823); (3) retire the transitional `ArtifactKind.core` in favour of a `has_layered_repository` capability predicate, widening the diagnostic surfaces to glossary_pack/skill/asset (#5824); (4) unify the pack-tier token under one kernel authority with an empty-allowlist gate (#5825/#5961); (5) delete the 13 dead `spec-kitty-standalone.md` copies, leaving `graph.yml` per its existing decision (#5322).

The whole mission is an exercise of **single canonical authority**: every new kind/tier fact derives from `ArtifactKind` or the new kernel tier authority — no hand-copied mirror, gates close with empty allowlists.

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**: typer, rich, ruamel.yaml (no new dependencies)
**Storage**: N/A (source + test + generated-copy files)
**Testing**: pytest; targeted blast radius per CLAUDE.md — `tests/charter/`, `tests/charter_offering/`, the specific named architectural gate files, and the owning module trees; `make test-fast` baseline. No full `tests/architectural/`/`test-full` sweep (NO_FULL_HEAVY_SUITES_IN_MISSION).
**Target Platform**: Cross-platform CLI
**Project Type**: single (library/CLI)
**Performance Goals**: N/A (no runtime hot path touched)
**Constraints**: empty-allowlist gates; `ruff`+`mypy --strict` clean; on-disk `packs/built-in/` and `_BUILT_IN_DIR_NAME` unchanged; no persisted provenance value broken; graph.yml untouched.
**Scale/Scope**: ~6 architectural-gate and authority files + ~6 kind-mirror sites + ~41 tier-token sites + 13 deletions.

## Charter Check

*GATE: Must pass before research. Re-check after design.*

- **Single canonical authority (DIRECTIVE_044)** — PASS by design: this is the mission's whole point. Every fact derives from one owner.
- **Architectural gate discipline (DIRECTIVE_043) + empty-allowlist ratchet (ADR 2026-09-30-1)** — PASS: every gate extended/added closes empty; each rule has a non-vacuous self-mutation test; a gate-unmask cannot self-validate.
- **Test remediation / red-first (DIRECTIVE_041, C-011 ATDD)** — PASS: each gate rule lands its failing case first; no skip/disable/xfail/retry-to-green.
- **Smallest viable diff + locality (DIRECTIVE_024/025)** — PASS with a hard out-of-scope fence (#5323, #4400, #5959, #5960, #5826).
- **Canonical sources + terminology (DIRECTIVE_044)** — PASS: no `doctrine`-tier vocabulary reintroduced; terminology guard run.
- **Decision documentation (DIRECTIVE_003)** — PASS: four material scope decisions recorded as resolved Decision Moments; the `core` retirement, surface-#4 widening, tier-spelling direction and graph.yml call captured.

No violations → Complexity Tracking empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/charter-kind-tier-vocab-closeout-01M4H5RF/
├── spec.md              # done (committed e7763f3)
├── plan.md              # this file
├── checklists/requirements.md
└── tasks/               # WP outline + packages (/spec-kitty.tasks)
```

### Source Code (repository root)

```
src/charter/offering/artifact_kinds.py      # authority: add has_layered_repository; delete core/_CORE_KINDS/CORE_KIND_PLURALS
src/charter/offering/packs/pack_manifest.py  # R1′ RECOGNISED_ARTIFACT_DIRS
src/charter/offering/packs/pack_assembler.py # R4 _ARTIFACT_DIRS_AND_GLOBS
src/charter/activation/context_renderers/fetch_stanza.py  # R1′ _VALID_SELECTOR_KINDS
src/charter/activation/consistency_check.py  # R5 _CLI_KIND_TO_DRG_SINGULAR
src/charter/activation/synthesizer/{project_drg.py,topic_resolver.py}  # R6 + SYNTHESIZABLE_KINDS home
src/specify_cli/mission_step_contracts/executor.py  # R6 _ARTIFACT_TO_NODE_KIND
src/charter/{bundle.py,...}, src/specify_cli/cli/commands/charter/_synthesis.py  # 3-kind subset restatements
src/specify_cli/cli/commands/_charter_pack_collect.py  # core surfaces #1+#2 (_ORG_ARTIFACT_DIRS)
src/specify_cli/charter_runtime/lint/checks/org_layer.py  # core surface #3
src/specify_cli/charter_packs/sources/api_source.py  # core surface #4 (widen)
src/specify_cli/upgrade/migrations/_charter_pack_cutover_snapshots.py  # DEFAULT_KIND_GATE isolation
src/kernel/pack_tiers.py (NEW)               # pack-tier token authority
src/charter/offering/pack_paths.py, pack_skills/{validation,repository}.py, activation/pack_manager.py, ... # tier-token sites
<13 generated agent dirs>/spec-kitty-standalone.md  # delete

tests/architectural/test_charter_kind_vocabulary_single_authority.py  # R1′/R4/R5/R6 rules + self-tests
tests/architectural/test_charter_facades_reexport_offering.py          # non-class identity coverage + self-test
tests/architectural/test_pack_tier_token_single_authority.py (NEW)     # tier-token gate
tests/charter_offering/test_artifact_kinds.py                          # has_layered_repository unit tests
<targeted tests> for repointed surfaces (collision/lint/api-source)
```

**Structure Decision**: single-project library/CLI; `single_branch` topology — WP01→WP02→WP03 converge on `artifact_kinds.py` and the facade table, so sequential execution in one checkout avoids self-inflicted lane-merge conflicts. WP04/WP05 are independent but share a few files (`pack_manager.py`, `list_cmd.py`, `drg/merge.py`), sequenced to keep the kind-vocab gates green.

## Complexity Tracking

None — no charter violations to justify.

## Implementation Concern Map

> Concerns, not work packages. `/spec-kitty.tasks` turns these into executable WPs.

### IC-01 — Facade re-export gate: non-class coverage (#5836)

- **Purpose**: The facade identity gate silently skips re-exported non-class values (tuples/frozensets lack `__module__`), so a drifted kind-vocabulary constant could cross a facade unchecked. Close it so the kind gate's single-authority check is actually enforceable across the facade boundary.
- **Relevant requirements**: FR-001.
- **Affected surfaces**: `tests/architectural/test_charter_facades_reexport_offering.py` (`_untabled_reexports` + a new non-class self-test). Test-only.
- **Sequencing/depends-on**: none — the enabler; land first.
- **Risks**: must resolve a plain value's origin by object-identity scan of `_IDENTITY_REQUIRED_ORIGINS` modules without breaking the existing `__module__`-based class path; keep the existing planted-wrapper self-test green.

### IC-02 — Kind-vocabulary gate: R1′/R4/R5/R6 + synthesizable subset (#5823)

- **Purpose**: Teach the gate the five mirror shapes it misses and migrate every live site to derive from the authority, keeping the allowlist empty.
- **Relevant requirements**: FR-002..FR-007.
- **Affected surfaces**: the gate file (new classifier rules + self-mutation tests + a "leaves legitimate constructs alone" test); live sites `pack_manifest.py`, `fetch_stanza.py`, `pack_assembler.py`, `consistency_check.py`, `executor.py`, `synthesizer/project_drg.py`; 3-kind restatements (`bundle.py`, `write_pipeline.py`, `_synthesis.py`) onto `SYNTHESIZABLE_KINDS`.
- **Sequencing/depends-on**: IC-01 (facade enforcement must be real before trusting facade re-exports as the one authority object).
- **Risks**: false positives on six legitimate constructs (`DIRECT_WRITE_KINDS`, total `PROJECT_KIND_DIRS`, str→NodeKind `_KIND_BY_LEGACY_FIELD`, `Literal[...]` aliases, callable/NodeKind dispatch tables) — rules must be tightly scoped and proven to leave them alone. `RECOGNISED_ARTIFACT_DIRS` stays a facade re-export (charter.packs) and must remain tabled.

### IC-03 — Retire `core` via `has_layered_repository` (#5824)

- **Purpose**: Replace the transitional `core` with a capability predicate (11 kinds) and widen the four diagnostic surfaces to cover glossary_pack/skill/asset; delete `core`/`_CORE_KINDS`/`CORE_KIND_PLURALS` + facade re-export.
- **Relevant requirements**: FR-008..FR-011.
- **Affected surfaces**: `artifact_kinds.py` (new predicate + frozenset; deletions), `_charter_pack_collect.py`, `org_layer.py`, `api_source.py` (widen), `_charter_pack_cutover_snapshots.py` (isolate `DEFAULT_KIND_GATE`), facade table + `charter.drg` `__all__`.
- **Sequencing/depends-on**: IC-02 (shared `artifact_kinds.py` + facade table; land after the gate rules so a new frozenset is validated by the live gate).
- **Risks**: the fifth `CORE_KIND_PLURALS` usage (`DEFAULT_KIND_GATE`) must NOT get the topology predicate; the new `has_layered_repository` frozenset must not trip any IC-02 rule (it is enum-member-valued, no NodeKind values → safe).

### IC-04 — Pack-tier token single authority (#5825/#5961)

- **Purpose**: One kernel-owned pack-tier token (spelling `"built-in"`), every site deriving from it, net-new empty-allowlist gate; leave the on-disk directory and `_BUILT_IN_DIR_NAME` fixed.
- **Relevant requirements**: FR-012..FR-014, NFR-003.
- **Affected surfaces**: new `kernel/pack_tiers.py`; `pack_paths.py`/`presets.py` (`PackTier`), `pack_skills/{validation,repository}.py` (`Tier`, `_TIER_RANK`), `agent_profiles/repository.py` (`_LAYER_RANK`), provenance sites, `pack_manager.py` `_LAYER_SEGMENTS`, `list_cmd.py`; new gate `test_pack_tier_token_single_authority.py`.
- **Sequencing/depends-on**: largely independent of IC-01..03; coordinate shared files (`pack_manager.py`, `list_cmd.py`, `drg/merge.py`) to keep kind-vocab + built-in-location gates green.
- **Risks**: must split tier-sense `"built-in"` from the on-disk directory sense; verify no `"builtin"` provenance string is persisted/compared (snapshots, fixtures, serialized config) before changing it — if any is persisted, that site is excluded with a recorded rationale.

### IC-05 — Dead residue cleanup (#5322)

- **Purpose**: Delete the 13 dead `spec-kitty-standalone.md` generated copies (no regeneration path exists); leave `graph.yml` untouched.
- **Relevant requirements**: FR-015, C-004.
- **Affected surfaces**: 13 `*/spec-kitty-standalone.md` files. `graph.yml` explicitly NOT touched.
- **Sequencing/depends-on**: independent.
- **Risks**: confirm no `src/` reader and no manifest/ownership contract references the deleted copies; `command_installer.verify` treats them as unmanaged orphans (consent-gated), so deletion is the operator-approved remedy.
