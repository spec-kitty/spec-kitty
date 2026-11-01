# Mission Specification: Freeze the charter offering public contract surface

**Mission Branch**: `kitty/mission-charter-offering-surface-freeze-01M6BTTR`
**Created**: 2026-11-01
**Status**: Draft
**Input**: Issue [#6285](https://github.com/spec-kitty/spec-kitty/issues/6285) — "charter.offering extraction — Phase 1/4: enumerate and freeze the offering public contract surface", re-scoped by the 2026-10-19 amendment to ADR `2026-10-16-1` (nothing Python moves; the 4.0.0 GA leg is a frozen seam plus a green conformance corpus) and by the tracker triage note of 2026-10-19.

## Problem and grounding

The building blocks of the freeze already shipped in earlier missions (verified on `origin/main` @ `287a226cfe`):

- `src/charter/offering/api.py` is a curated 12-name manifest (`__all__`);
- `tests/architectural/test_charter_offering_public_surface.py` asserts importability, sorting, disposition coupling and facade routing;
- `tests/architectural/test_charter_facades_reexport_offering.py` asserts identity re-export through `charter.drg`, `charter.assets`, `charter.model_routing` and `charter.languages`;
- `tests/architectural/test_charter_offering_does_not_import_activation.py` asserts the zero-dependency direction.

What is **not** done, and is this mission's scope:

1. **No census is committed.** The surface is asserted against itself; nothing pins the exact symbol set. The gate's own docstring records this gap ("it does not additionally pin the exact symbol set as a frozen literal"). Adding or dropping an export today only requires editing the same file that advertises it.
2. **No per-symbol contract annotation.** There is no record of what each exported symbol's parameters and returns are today, nor of the ADR-0004 generated-DTO target with today's hand-written types marked transitional.
3. **No whole-picture classification.** The reached charter symbols are dispositioned by *path* in `tests/architectural/test_doctrine_census.py`, but nothing states, per exported symbol, PUBLIC vs FACADE-ONLY vs INTERNAL, and nothing proves that no runtime consumer is reaching a symbol that is absent from the frozen surface (the public-contract delta).
4. **C-003 is stale.** `api.py` still says "OpenAPI conventions do not apply", which is the position #6218 exists to reverse (spec-kitty-charter ADR-0004: the public API returns DTOs generated from the OpenAPI contract; core's hand-written types are transitional). #6285 instructs this mission either to land #6218 first or to fold its wording in.

The term "surface" in this mission always means **the in-process Python public contract of `charter.offering`** (the `charter.offering.api` manifest plus the facades that front it) — not an HTTP surface, and not the YAML artifact catalog.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A maintainer reads one committed census and knows the frozen surface (Priority: P1)

A maintainer planning the conformance corpus (P2, #6286) or the boundary gates (P3, #6287) opens one committed census file and sees, for every symbol the offering publishes: where it comes from, its disposition, which `charter.*` facade fronts it, what its parameters and returns are today, and what the generated-DTO target is. No symbol is on the surface that the census does not name, and no symbol is named that is not on the surface.

**Why this priority**: without the freeze there is nothing to conform *to*; P2 and P3 both consume this list.

**Independent Test**: The census file is committed and `tests/architectural/test_charter_offering_public_surface.py` fails when `charter.offering.api.__all__` gains, drops or reorders a name relative to it; a planted-mutation self-test proves the comparison can fail.

**Acceptance Scenarios**:

1. **Given** the committed census and the live `charter.offering.api.__all__`, **When** the gate runs, **Then** the two name lists are equal, in order, and every census row resolves to a real object on the module.
2. **Given** a new export is added to `api.__all__` without a census row, **When** the gate runs, **Then** it fails naming the unlisted symbol; **Given** a census row is removed while the export stays, **When** the gate runs, **Then** it fails naming the missing row.

---

### User Story 2 - A consumer author sees which types are transitional before building on them (Priority: P1)

Someone writing a consumer against the seam reads the census (and the C-003 note it points to) and learns that today's hand-written parameter and return types are transitional and will be replaced by contract-generated DTOs, per spec-kitty-charter ADR-0004. They do not build against a type that is silently promised to be permanent.

**Why this priority**: #6218 exists because a caller reading today's C-003 is misled about durability; the freeze is the moment the record becomes honest.

**Independent Test**: Every census row carries a non-empty `today_type` and `dto_target`, a `dto_status` of `transitional`, and a `contract_kind`; the gate fails on a row that omits any of them. C-003 in `api.py` states the DTO direction and no longer says OpenAPI conventions do not apply.

**Acceptance Scenarios**:

1. **Given** the 12 exported symbols, **When** the gate validates the census, **Then** every row is fully annotated in the ADR-0004 direction and none claims a permanent hand-written type.
2. **Given** a row with `dto_status: final`, **When** the gate runs, **Then** it fails — nothing on this surface is final until the contract work lands.

---

### User Story 3 - A reviewer can see the whole reached-symbol picture and the delta (Priority: P2)

A reviewer asking "is anything a runtime consumer needs still missing from the frozen surface?" reads the census's classification section: every reached charter path is PUBLIC, FACADE-ONLY or INTERNAL, keyed to the authoritative disposition manifest, and the public-contract delta (reached symbols not on the frozen surface) is enumerated. It is currently expected to be empty; anything found is reported for operator approval, never widened silently.

**Why this priority**: the issue requires the classification and the delta, but a non-empty delta is an operator decision, not an implementer one.

**Independent Test**: The gate recomputes the reached-path set from the live tree and fails when a reached path is neither classified in the census section nor absent from the frozen surface by design; a planted-mutation self-test proves the probe can see a delta.

**Acceptance Scenarios**:

1. **Given** the live tree, **When** the classification check runs, **Then** every reached offering path resolves to a census classification that matches `test_doctrine_census.DISPOSITION`.
2. **Given** a runtime module starts reaching a new offering path not on the frozen surface, **When** the gate runs, **Then** it reports the path as a delta rather than passing silently.

---

### Edge Cases

- **A symbol is on the surface but no facade re-exports it.** The existing strict coverage assertion already fails; the census must not provide a bypass. The census row's `facades` list must equal the dynamically discovered re-exporters.
- **A facade re-exports a name from `charter.offering.api` that is not in the census.** Fail as surface drift, naming the facade and symbol.
- **`LANGUAGE_TOKENS` is a constant, not a callable.** Its "type" is the constant's value type; the census records it as a value, not as a call target, and the gate must not require a callable signature for it.
- **`charter.offering.api` imports from a submodule whose disposition is keyed at package level** (e.g. `charter.offering.model_task_routing`). The disposition lookup must resolve by longest prefix, as the existing gate does.
- **The census file is missing or unparsable.** Fail loudly with the path — an empty census must never make the freeze vacuous.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Committed machine-readable census | As a maintainer, I want one committed census of the offering public surface so that the frozen contract has a single named source. | High | Open | [build] | no — the census file must exist, parse, and enumerate exactly the live surface |
| FR-002 | Surface pinned to the census | As a maintainer, I want the gate to compare `charter.offering.api.__all__` with the census in both directions and in order so that an export cannot be added or dropped without a census change. | High | Open | [build] | no — a planted unlisted export and a planted missing row both fail |
| FR-003 | Facades proven against the census | As a reviewer, I want each census row's facade list to equal the facades that actually re-export it by identity so that the one canonical list and the facades cannot drift. | High | Open | [build] | no — a planted extra facade re-export fails the comparison |
| FR-004 | Per-symbol DTO-forward annotation | As a consumer author, I want every row annotated with contract kind, today's type and the generated-DTO target, with today's types marked transitional, so that I know what will change. | High | Open | [build] | no — a row missing an annotation, or claiming a final hand-written type, fails |
| FR-005 | Whole-picture classification and delta | As a reviewer, I want every reached charter path classified PUBLIC / FACADE-ONLY / INTERNAL against the authoritative disposition manifest, and the public-contract delta enumerated, so that nothing widens silently. | High | Open | [build] | no — a reached path that the census does not classify is reported as a delta |
| FR-006 | C-003 carries the ADR-0004 direction | As a consumer author, I want `api.py`'s C-003 to say the seam's return types become contract-generated DTOs and today's types are transitional, so that the module stops asserting the opposite. | High | Open | [build] | no — the stale "OpenAPI conventions do not apply" wording must be gone |
| FR-007 | Zero offering→activation dependency retained | As a maintainer, I want the existing no-import-activation gate to stay green and unmodified in its assertions so that the freeze does not smuggle in the forbidden edge. | Medium | Open | [ratchet] | no — the gate must exist and pass; a planted offering→activation import is still caught |
| FR-008 | Changelog and docs pointer | As a maintainer, I want an `[Unreleased]` changelog entry and a documentation pointer to the census, so that the freeze is discoverable and reviewable. | Medium | Open | [build] | no — the entry must lead with impact and the offering README must carry the pointer |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Gate cost | The census checks add under 8.0 s of wall time to the gate file, measured locally with `time uv run pytest <gate file>`; the dominant cost is the single authoritative reached-path scan, cached once per process, and no second scanner is introduced. | Performance | Medium | Open |
| NFR-002 | Deterministic and offline | The census is read from the committed file; the checks perform no network access and no clock/locale-dependent comparison. | Reliability | High | Open |
| NFR-003 | Static quality | `ruff check` and `mypy` are clean on every changed Python file and the changed functions stay at or below cyclomatic complexity 15. | Maintainability | High | Open |
| NFR-004 | No gate duplication | Each invariant keeps exactly one owning gate file; the census is validated inside the existing gates rather than by a parallel new gate that could disagree with them. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No Python moves | Nothing under `src/charter/offering/` moves or changes package; per the 2026-10-19 ADR amendment the offering stays in core. | Technical | High | Open |
| C-002 | No gate weakening | No `skip`, `xfail`, allowlist widening or assertion loosening in the gate files; new checks are additive. | Technical | High | Open |
| C-003 | No silent widening | Any symbol a consumer needs that is absent from the surface is reported as a public-contract delta for operator approval; this mission does not add it. | Business | High | Open |
| C-004 | #6218 stays distinct | The wording direction from #6218 is folded in here as the C-003 amendment; the issue itself is not closed or absorbed, and no DTO generation is implemented. | Business | Medium | Open |

### Key Entities

- **Census row**: one exported `charter.offering.api` symbol — name, origin module, disposition (PUBLIC), facade modules that re-export it from `charter.offering.api`, contract kind, today's type, generated-DTO target, DTO status.
- **Classification row**: one reached `charter.offering` module path — path, disposition (PUBLIC / FACADE-ONLY / INTERNAL), and whether it is on the frozen surface.
- **Public-contract delta**: a reached charted symbol that a runtime consumer needs and that is absent from the frozen surface; expected empty, operator-gated when not.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A single committed census file enumerates all 12 exported symbols, and `uv run pytest -q tests/architectural/test_charter_offering_public_surface.py` fails when a name is added, dropped or reordered relative to it (proven by a planted-mutation self-test) — [build] · no-op passable: no
- **SC-002**: 100% of census rows carry contract kind, today's type, generated-DTO target and `transitional` status; 0 rows claim a final hand-written type — [build] · no-op passable: no
- **SC-003**: Every reached offering path is classified and matches `test_doctrine_census.DISPOSITION`; the enumerated public-contract delta is empty, or each entry is listed for operator approval — [build] · no-op passable: no
- **SC-004**: `make test-fast`, `tests/charter/`, `tests/charter_offering/`, the three named gate files and the docs-freshness check are green (baseline 0 errors), with ruff and mypy clean — [ratchet] · no-op passable: no
