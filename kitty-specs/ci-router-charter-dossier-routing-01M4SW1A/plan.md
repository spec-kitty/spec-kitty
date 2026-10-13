# Implementation Plan: CI router selects charter + dossier for mission-manifest edits

**Branch**: `issue-6125-ci-router-charter-dossier-routing` | **Date**: 2026-10-13 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/ci-router-charter-dossier-routing-01M4SW1A/spec.md`

## Summary

Close the #6125 per-PR → red-main routing gap: an edit to a mission's
`packs/built-in/missions/*/expected-artifacts.yaml` must select the `charter` **and**
`dossier` test modules. Technical approach (grounded in
[research/code-grounding.md](./research/code-grounding.md)): add the **file-specific**
glob `packs/built-in/missions/**/expected-artifacts.yaml` to the `charter` group and a
newly-minted `dossier` module group, in all three verbatim-coupled authorities (scrub
roots, registry roots, router filter) in lockstep; mint `dossier` as a real module with
`test_dirs` `[tests/dossier, tests/specify_cli/dossier]`, released from
`out_of_matrix_test_dirs`; capture real measured shard timings. Pinned by an ATDD
router-parity test proven RED on `origin/main`.

## Technical Context

**Language/Version**: Python 3.11+ (test + CI-config change; no product code)
**Primary Dependencies**: `scripts/ci/gate_selection.py` (routing authority), `pyyaml`, `pytest`
**Storage**: N/A — the authorities are on-disk YAML/JSON (`ci-router.yml`, `ci-module-registry.yml`, `ci_retirement_scrub.json`, `ci-shard-timings.json`)
**Testing**: pytest; the new gate lives beside the existing router/registry gates in `tests/architectural/`; `make test-fast` + the specific named CI gate files (never a `tests/architectural/` sweep, per `NO_FULL_HEAVY_SUITES_IN_MISSION`)
**Target Platform**: GitHub Actions CI (Linux runners)
**Project Type**: single (CLI repo)
**Performance Goals**: N/A (routing config); `dossier` shard_count chosen so no shard exceeds the per-shard timeout
**Constraints**: router verbatim guard (C-001), file-specific glob only (C-002), no product code (C-003)
**Scale/Scope**: ~5 files edited; one new registry row + one new scrub group + one new router filter group + one measured timings entry + one new test file

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **ATDD-first (C-011)**: PASS — FR-001 is a red-first parity test committed before the
  routing change; reviewer verifies RED on base, GREEN on final.
- **Architectural gate discipline (Standing Order #5)**: PASS — the parity test is a
  non-vacuous call-site gate (a self-break, e.g. dropping the glob, flips it red); it
  adds no allowlist, so no baseline entry is needed (ADR 2026-09-30-1).
- **Single canonical authority (NFR-001)**: PASS — registry/scrub/router stay verbatim
  in lockstep; no second path→group map.
- **No new size/length ratchet (NFR-002)**: PASS — routing gate only (operator ruling).
- **No product code (C-003)**: PASS — CI wiring + tests only.
- **Terminology canon**: PASS — no new user-facing surface; "Mission" vocabulary preserved.

No violations → Complexity Tracking left empty.

## Project Structure

### Documentation (this mission)

```
kitty-specs/ci-router-charter-dossier-routing-01M4SW1A/
├── spec.md
├── plan.md                       # this file
├── research/code-grounding.md    # empirical grounding + guard map
├── tasks.md                      # Phase 2 (/spec-kitty.tasks)
├── tasks/                        # WP files
├── tooling-friction.md           # tracer
├── approach.md                   # tracer
└── design-decisions.md           # tracer
```

### Source Code (repository root)

```
.github/
├── ci-module-registry.yml        # add `dossier` row; append manifest glob to `charter` roots; drop dossier dirs from out_of_matrix
├── workflows/ci-router.yml        # add `dossier` filter group + output + unmatched-loop + heavy-battery gate; append manifest glob to `charter` filter
└── ci-shard-timings.json          # measured `dossier` capture (via capture_shard_timings.py)

tests/
├── release/ci_retirement_scrub.json          # add `dossier` group; append manifest glob to `charter` roots
└── architectural/test_manifest_edit_routes_charter_and_dossier.py   # NEW red-first parity gate
```

**Structure Decision**: Single-project CLI repo. The change is confined to the CI
routing authorities under `.github/` + `tests/release/ci_retirement_scrub.json`, plus a
new gate test under `tests/architectural/` (co-located with the sibling router/registry
gates `test_gate_selection_authority.py`, `test_module_shard_registry.py`,
`test_ci_router_transcription_guards.py`). No `src/**` changes.

## Complexity Tracking

*No Charter Check violations — not applicable.*

## Implementation Concern Map

> Concerns are not work packages. `/spec-kitty.tasks` translates these into executable WPs.

### IC-01 — Red-first router-parity gate

- **Purpose**: Pin the user-observable contract (a mission-manifest diff selects
  charter+dossier) with a non-vacuous ATDD gate, proven RED on base.
- **Relevant requirements**: FR-001; SC-001.
- **Affected surfaces**: `tests/architectural/test_manifest_edit_routes_charter_and_dossier.py` (new).
- **Sequencing/depends-on**: none (lands first, RED).
- **Risks**: Must assert through the real authority `select_modules` (not a hand map), and
  prove RED on `origin/main` to avoid a vacuous gate.

### IC-02 — Charter leg (route the manifest glob to the charter module)

- **Purpose**: Make a manifest edit select the `charter` module by adding the
  file-specific glob to the `charter` group in all three verbatim authorities.
- **Relevant requirements**: FR-002; NFR-001, C-001, C-002.
- **Affected surfaces**: `tests/release/ci_retirement_scrub.json` (`charter` roots),
  `.github/ci-module-registry.yml` (`charter` roots), `.github/workflows/ci-router.yml`
  (`charter` filter).
- **Sequencing/depends-on**: IC-01 (turns the gate's charter half green).
- **Risks**: Ordered-append in all three (verbatim guard is list-equality); keep the glob
  file-specific so the corpus golden (`foo.md`) stays green.

### IC-03 — Dossier module leg (mint the module + route it)

- **Purpose**: Give `tests/dossier` + `tests/specify_cli/dossier` a real per-PR module,
  route both dossier-source and manifest edits to it, and capture measured timings.
- **Relevant requirements**: FR-003, FR-004, FR-005; NFR-001, NFR-003.
- **Affected surfaces**: `tests/release/ci_retirement_scrub.json` (new `dossier` group),
  `.github/ci-module-registry.yml` (new row + `out_of_matrix_test_dirs` removal),
  `.github/workflows/ci-router.yml` (new filter group + `changes.outputs` + `unmatched`
  loop + heavy-battery `if:`), `.github/ci-shard-timings.json` (measured capture).
- **Sequencing/depends-on**: IC-01 (turns the gate's dossier half green); the registry row
  must exist before `capture_shard_timings.py --module dossier` can measure it.
- **Risks**: bijection + verbatim + claim-once guards; src-backed group must join the
  unmatched union + heavy-battery gate; shard-timings must be measured (committed ==
  collected), never guessed.
