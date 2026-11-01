# Implementation Plan: Freeze the charter offering public contract surface

**Branch**: `kitty/mission-charter-offering-surface-freeze-01M6BTTR` | **Date**: 2026-11-01 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/charter-offering-surface-freeze-01M6BTTR/spec.md`
**Issue**: [#6285](https://github.com/spec-kitty/spec-kitty/issues/6285) (P1 of epic #6099)

## Summary

Commit one machine-readable census of the charter offering public surface, pin the
existing live surface to it in the gates that already own each invariant, annotate
every exported symbol in the ADR-0004 generated-DTO direction, and record the
reached-symbol classification plus the (expected-empty) public-contract delta.
The only code touched is `src/charter/offering/api.py`'s C-003 docstring —
nothing moves, no DTO is generated, no gate is weakened.

## Technical Context

**Language/Version**: Python 3.11 (repo floor), `from __future__ import annotations` in force
**Primary Dependencies**: PyYAML (already a test dependency), pytest, `tests.architectural.test_doctrine_census` (authoritative disposition manifest), `tests.architectural.test_charter_facades_reexport_offering._FACADE_TABLE` (authoritative identity table)
**Storage**: one committed YAML census file under `tests/architectural/`
**Testing**: pytest, architectural lane; census checks run inside the two existing gate files that already own the invariants (`test_charter_offering_public_surface.py`, `test_charter_facades_reexport_offering.py` untouched), with planted-mutation self-tests for non-vacuity
**Target Platform**: any; no platform-specific behaviour
**Project Type**: single Python package (`src/charter/offering`) + architectural gates
**Performance Goals**: the new checks add < 8.0 s to the gate file — one YAML read, one module import, and one authoritative reached-path scan cached per process (the scan, not the census, is the cost; a second scanner would be a forbidden second source of truth)
**Constraints**: no network, no clock/locale dependence, no `src/charter/offering` file moves, no assertion loosening, complexity ≤ 15
**Scale/Scope**: 12 exported symbols, 10 reached offering paths, 6 reaching files

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | How this plan satisfies it |
|---|---|
| Single canonical authority | One census file is the frozen list; `api.__all__` and the facade table are pinned to it. The disposition manifest stays the single authority for classification; the census references it and the gate compares, never restates. |
| Architectural alignment | No new layer, module move or import direction change. `charter.offering` keeps zero runtime dependency on `charter.activation`. |
| ATDD-first / red-first | Freeze assertions are authored before the census exists and are proven red, then green; planted-mutation self-tests prove each new assertion can fail (architectural-gate non-vacuity). |
| Terminology canon | "surface" always means the in-process Python public contract of `charter.offering` (stated in the census header); "Mission", never "feature". |
| `__all__` Declaration Convention (C-007) | `__all__` stays a literal in `api.py`; the census pins it rather than generating it, so static parsers keep working. |
| Standing Order #5 / burn-down | No new allowlist or baseline entry. The census is a frozen contract, not a ratchet; the delta list is asserted empty. |
| `NO_FULL_HEAVY_SUITES_IN_MISSION` | Only the named gate files, `tests/charter/`, `tests/charter_offering/` and `make test-fast` run locally. |
| Pre-existing Failure Reporting Rule | The docs-freshness baseline shows 0 errors / 13 warnings today; only regressions against that baseline are this mission's problem. |

No Charter Check violations → no Complexity Tracking entries.

## Project Structure

### Documentation (this mission)

```
kitty-specs/charter-offering-surface-freeze-01M6BTTR/
├── plan.md              # this file
├── research.md          # Phase 0 output (discovery decisions D-001..D-005)
├── data-model.md        # Phase 1: census row / classification row / delta
├── quickstart.md        # Phase 1: reproduce and verify
├── contracts/
│   └── public-surface-census.md   # Phase 1: census field contract + invariants
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```
src/charter/offering/
├── api.py                     # C-003 reworded (ADR-0004 direction); __all__ untouched
└── README.md                  # + "Public contract surface" section pointing at the census

tests/architectural/
├── charter_offering_public_surface.yaml        # NEW — the frozen census (machine truth)
├── test_charter_offering_public_surface.py     # + census pin, annotations, classification, delta, self-tests
├── test_charter_facades_reexport_offering.py   # unchanged (table read by the census gate)
├── test_charter_offering_does_not_import_activation.py   # unchanged (retained ratchet, FR-007)
└── test_charter_activation_api_reexport.py     # unchanged

docs/changelog/CHANGELOG.md    # [Unreleased] entry
```

**Structure Decision**: single project. The census lives beside the gate that reads
it, mirroring `tests/architectural/charter_activation_boundary_baseline.yaml`; it is a
review artefact and test fixture, never wheel data.

## Design

### Census file (`tests/architectural/charter_offering_public_surface.yaml`)

Header:

```yaml
schema_version: "1.0"
surface: chart.offering public contract surface   # the in-process Python contract
mission: charter-offering-surface-freeze-01M6BTTR
issue: 6285
frozen_at: "2026-11-01"
c003: >                                        # the one restatement, quoting #6218's direction
  The seam's return types become contract-generated DTOs (spec-kitty-charter ADR-0004);
  hand-written types recorded below are transitional.
surface:                                       # 12 rows, one per api.__all__ name
  - name: <Symbol>
    origin: <module the api imports it from>
    disposition: PUBLIC
    facades: [<charter facade modules that re-export it from charter.offering.api>]
    contract_kind: enum|model|exception|protocol|dataclass|constant|function
    today_type: <one-line description of the current hand-written type>
    signature: <exact inspect.signature() string for callables, null otherwise>
    dto_target: <the generated-DTO direction for this symbol>
    dto_status: transitional
reached_classification:                        # every reached offering path
  - path: charter.offering.artifact_kinds
    disposition: PUBLIC
    on_surface: true
    consumers: [src/...]
public_contract_delta: []                      # asserted empty; anything here is operator-gated
```

### Checks added to `test_charter_offering_public_surface.py`

| Check | Invariant | Red proof |
|---|---|---|
| `test_census_enumerates_exactly_the_live_surface` | `[row.name …] == api.__all__` (order included) | planted: drop a row / add a name |
| `test_census_origin_and_disposition_match_the_module` | each `origin` equals the AST-declared import origin; `disposition == DISPOSITION[longest-prefix] == "PUBLIC"` | planted: wrong origin string |
| `test_census_facades_match_the_identity_table` | each row's `facades` equals the facade modules in `_FACADE_TABLE` whose source is `charter.offering.api` and whose symbol is this name | planted: extra/missing facade |
| `test_every_surface_row_is_dto_forward_annotated` | `contract_kind` matches the runtime object kind; `today_type`/`dto_target` non-empty; `dto_status == "transitional"`; `signature` equals `inspect.signature()` for callables | planted: `dto_status: final`, empty `today_type` |
| `test_reached_paths_are_classified_and_delta_is_empty` | every reached path has a row; row disposition equals `DISPOSITION`; `on_surface` matches the surface origins; computed delta equals the declared `public_contract_delta` (empty) | planted: unknown reached path |
| `test_census_is_not_vacuous` | the census parses, has 12 rows, and a mutated copy fails the name-set comparison (positive control for the freeze) | inherent |

Checks are deliberately added to the existing gate file rather than a new one: that
file already owns importability/sorting/disposition/facade-routing, and a second gate
could disagree with it (NFR-004). No existing assertion is changed or removed.

## Implementation Concern Map

### IC-01 — Frozen census and its gate checks

- **Purpose**: Give the offering surface one committed, reviewable, machine-checked list so the conformance corpus (P2) and boundary gates (P3) have something to conform to.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001, NFR-002, NFR-004, C-001, C-002, C-003
- **Affected surfaces**: `tests/architectural/charter_offering_public_surface.yaml` (new), `tests/architectural/test_charter_offering_public_surface.py`
- **Sequencing/depends-on**: none
- **Risks**: pinning `inspect.signature()` strings can churn on annotation refactors — accepted deliberately (that is the freeze); `_FACADE_TABLE` is a private table, so the gate must fail loudly if its shape changes rather than pass vacuously.

### IC-02 — Contract record: C-003, offering README, changelog

- **Purpose**: Stop the module from asserting the opposite of spec-kitty-charter ADR-0004, and make the frozen surface discoverable to a maintainer who never opens the gate file.
- **Relevant requirements**: FR-006, FR-008, C-004
- **Affected surfaces**: `src/charter/offering/api.py` (docstring only), `src/charter/offering/README.md`, `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: IC-01 (the census `c003` note and the docstring must say the same thing)
- **Risks**: #6218 owns the ADR alignment framing; this concern must not close it, must not restate the ADR, and must not imply DTO generation has landed. A terminology gate (`test_no_legacy_terminology.py`) and docs freshness must stay green.

## Verification plan

```bash
uv run pytest -q tests/architectural/test_charter_offering_public_surface.py \
                 tests/architectural/test_charter_facades_reexport_offering.py \
                 tests/architectural/test_charter_activation_api_reexport.py \
                 tests/architectural/test_charter_offering_does_not_import_activation.py
uv run pytest -q tests/charter tests/charter_offering
uv run pytest -q tests/architectural/test_no_legacy_terminology.py
make test-fast
uv run ruff check <changed files>
uv run mypy <changed files>
uv run python -m scripts.docs.check_docs_freshness --ci   # baseline: errors=0
```
