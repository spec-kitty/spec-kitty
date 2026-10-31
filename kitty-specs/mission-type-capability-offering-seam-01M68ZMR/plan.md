# Implementation Plan: Mission-type capability contract on the offering seam

**Branch**: `issue-6331-mission-type-capability-offering-seam` | **Date**: 2026-10-31 | **Spec**: [spec.md](./spec.md)
**Input**: Mission specification from `kitty-specs/mission-type-capability-offering-seam-01M68ZMR/spec.md`

## Summary

Expose the mission-type capability contract (`wp_driven`, `requires_substantive_spec`) on the
named charter offering seam `charter.offering.api`, so a consumer can read both capabilities
without importing `charter.activation.*`. The exposure is a new offering module
(`charter/offering/missions/capabilities.py`) carrying a frozen value object, a
runtime-checkable protocol and one read function; activation's `ResolvedMissionType` satisfies
the protocol structurally and hands back the value object; `charter.missions` re-exports the
three symbols from `charter.offering.api`. The activation-side resolver is **not** re-exported:
ADR 2026-10-16-1 (Amendment 2026-10-19) records a verified zero-edge dependency direction
(`charter.offering` → `charter.activation` = 0; the reverse ≈ 360), and a re-export would invert
it. Additive seam symbols follow the ADR 2026-10-03-1 amendment path already used for
`LANGUAGE_TOKENS` (#6541).

## Technical Context

**Language/Version**: Python 3.11+ (`from __future__ import annotations`, stdlib `typing.Protocol`)
**Primary Dependencies**: none new. The new module imports only `dataclasses` and `typing`; it
must not import `charter.activation`, `pydantic`, or any I/O module.
**Storage**: N/A — the module is pure in-memory; capability values are read off the object in hand.
**Testing**: pytest. Fast lane for the seam test (`pytestmark = pytest.mark.fast`), architectural
lane for the gate files, plus the existing mission-type profile suite unchanged.
**Target Platform**: Linux/macOS CPython (the repository's supported matrix).
**Project Type**: single Python package (`src/charter`, `src/specify_cli`, `src/runtime`).
**Performance Goals**: no new hot-path work. `capabilities_of()` reads two already-resolved
attributes; the `requires_substantive_spec` read stays behind the existing memoised
`cached_property`, so the mission-type resolution hot path gains zero disk reads.
**Constraints**: `charter.offering.*` must not import `charter.activation.*` (C-001);
`charter.offering.api.__all__` stays sorted and grows by exactly three entries (NFR-003);
no change to capability semantics (C-002).
**Scale/Scope**: one new 3-symbol module, one property on `ResolvedMissionType`, three facade
re-exports, one census row, one ADR amendment, one changelog entry, one new test file.

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Charter rule | Verdict | Note |
|---|---|---|
| Single canonical authority (C-001 charter) | PASS | The capability values keep exactly one producer: `ResolvedMissionType`'s own attributes. The seam read derives from them (spec C-004); no capability table is copied into offering. |
| Architectural alignment: Shared Package Boundary / ADR 2026-10-16-1 | PASS | The change adds no offering → activation edge; FR-007 tests it in a subprocess with a positive control. |
| ATDD-first (C-011) | PASS | The seam test is written first and fails on the pre-change tree (ImportError on `charter.offering.api.MissionTypeCapabilities`). |
| `__all__` declaration convention (C-007) | PASS | Every new public module declares `__all__`; the seam manifest stays sorted. |
| Directive 044 — canonical sources | PASS | The seam is `charter.offering.api`; the facade pattern and the ADR amendment format are copied from the in-repo `LANGUAGE_TOKENS` precedent, not invented. |
| DIRECTIVE_024 Locality of Change | PASS | Four source files touched, each the minimum: the new module, the activation DTO, the seam manifest, the facade. |
| Terminology canon | PASS | Uses "mission type", "capability", "offering seam"; no `feature*` vocabulary introduced. |

## Project Structure

### Documentation (this mission)

```
kitty-specs/mission-type-capability-offering-seam-01M68ZMR/
├── plan.md              # This file
├── research.md          # Phase 0 (discovery findings)
├── data-model.md        # Phase 1
├── contracts/
│   └── mission-type-capabilities-contract.md   # Phase 1
├── spec.md
└── tasks/               # Phase 2 (/spec-kitty.tasks)
```

### Source Code (repository root)

```
src/charter/offering/missions/capabilities.py     # NEW — the contract on the seam
src/charter/offering/api.py                       # +3 manifest entries
src/charter/missions.py                           # facade re-exports the 3 symbols from the seam
src/charter/activation/mission_type_profiles.py   # ResolvedMissionType.capabilities property
tests/charter_offering/test_mission_type_capabilities_seam.py   # NEW — red-first seam proof
tests/architectural/test_doctrine_census.py       # +1 PUBLIC disposition row
docs/adr/4.x/2026-10-03-1-charter-read-write-service-strangler.md  # amendment (seam addition)
docs/changelog/CHANGELOG.md                       # [Unreleased] entry
```

**Structure Decision**: single package layout, no new package. The new module sits beside the
other `charter.offering.missions.*` modules it is a contract for; it deliberately has no
subpackage of its own so the census key stays one row.

## Phase 0 — Research (see `research.md`)

Complete. Decisions D1–D4 and the resolved open questions are recorded there; no
`NEEDS CLARIFICATION` remains.

## Phase 1 — Design

### Data model

See `data-model.md`. Three symbols, no persistence, no state:

- `MissionTypeCapabilities` — frozen dataclass, two booleans, both defaulting `False`
  (conservative: an undeclared capability is never assumed).
- `MissionTypeCapabilitySource` — `@runtime_checkable` `Protocol` with read-only
  `wp_driven` and `requires_substantive_spec` properties.
- `capabilities_of(source)` — the one read; returns the value object, failing loudly
  (`AttributeError`) on a non-conforming source rather than defaulting.

### Contract

See `contracts/mission-type-capabilities-contract.md` for the exact seam surface, the
conformance rules, and the invariants the gates enforce.

### Design decisions carried into tasks

1. **No resolver on the seam.** `resolve_mission_type_context` stays in
   `charter.activation`; the seam exposes the *contract*, and a consumer in the activation tier
   (or one handed a resolved bundle) reads capabilities through it.
2. **Protocol first, value object second.** #6327 adds `code_producing`. A protocol is stable
   under that addition; a tuple or a re-exported class is not.
3. **`capabilities_of` is strict.** A source missing a capability raises; silent `False`
   defaults on a non-conforming object would be the same fail-open shape #6330 is closing.
4. **The DTO's `capabilities` property is additive and memoised-free.** It builds a 2-field
   frozen value from two reads already on the object; a `cached_property` would add state for
   no gain.
5. **The facade is the door.** `charter.missions` re-exports from `charter.offering.api`
   (object identity), satisfying the strict coverage gate, exactly as `charter.languages` does
   for `LANGUAGE_TOKENS`.

## Complexity Tracking

No Charter Check violations.

## Implementation Concern Map

### IC-01 — The capability contract module on the seam

- **Purpose**: Define the consumer-facing capability contract inside `charter.offering` so it
  crosses the seam without importing activation.
- **Relevant requirements**: FR-001, FR-002, FR-003, FR-008 (typeless/custom reads), C-001, C-004
- **Affected surfaces**: `src/charter/offering/missions/capabilities.py` (new)
- **Sequencing/depends-on**: none
- **Risks**: a `TypedDict`/tuple shape would not survive #6327; keep the protocol + frozen
  dataclass. `runtime_checkable` protocols check attribute presence only — the negative control
  in the test must therefore use an object that *lacks* a capability entirely, not one with the
  wrong type.

### IC-02 — Wire the seam and the door

- **Purpose**: Publish the three symbols on `charter.offering.api`, re-export them from the
  `charter.missions` facade, and let `ResolvedMissionType` satisfy the contract.
- **Relevant requirements**: FR-004, FR-005, NFR-003, C-002, C-003
- **Affected surfaces**: `src/charter/offering/api.py`, `src/charter/missions.py`,
  `src/charter/activation/mission_type_profiles.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: the strict facade-coverage gate fails for any seam symbol without a facade
  re-export; `test_charter_facades_reexport_offering.py` pins object identity. Touching
  `mission_type_profiles.py` is the only overlap with #6327 — the property is added beside the
  existing capability properties, not beside the capability *fields*, to keep the hunks apart.

### IC-03 — Gates, proof and record

- **Purpose**: Make the addition honest: census disposition, layering proof, seam test, ADR
  amendment and changelog.
- **Relevant requirements**: FR-006, FR-007, NFR-001, NFR-002, SC-001..SC-004
- **Affected surfaces**: `tests/architectural/test_doctrine_census.py`,
  `tests/charter_offering/test_mission_type_capabilities_seam.py` (new),
  `docs/adr/4.x/2026-10-03-1-charter-read-write-service-strangler.md`,
  `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: IC-01, IC-02
- **Risks**: the census gate must be satisfied by a `PUBLIC` row, never by loosening the gate;
  the layering test must run the import in a **fresh subprocess** (an in-process check would
  pass vacuously because earlier tests already imported activation).
