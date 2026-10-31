# Mission Specification: Glossary — activation ledger and active charter

**Mission Branch**: `issue-6562-glossary-activation-ledger`
**Created**: 2026-10-31
**Status**: Draft
**Input**: spec-kitty/spec-kitty#6562 — "Glossary: add 'activation ledger' and update 'active charter' in spec-kitty-core". After #6496 moved activation into `.kittify/charter/activation.yaml`, the core glossary still lacks an `activation ledger` term and its `active charter` definition still names the old `config.yaml` / `charter.yaml` location.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — An operator looks up "activation ledger" (Priority: P1)

An operator who has just run `spec-kitty upgrade` sees `.kittify/charter/activation.yaml` in their diff and opens the published glossary to find out what it is. Today there is no entry, so they have to read the ADR and the CLI reference.

**Why this priority**: The ledger became the single activation authority in #6496; the glossary is the canonical place that names it. Without the term, every reader rediscovers it from source or ADR.

**Independent Test**: Search the published glossary data (`.kittify/glossaries/spec_kitty_core.yaml`) and the built-in glossary pack for the surface `activation ledger`; both carry an active definition that names the ledger file, the allow/deny state and the "not the Migration Ledger" distinction.

**Acceptance Scenarios**:

1. **Given** the core glossary seed on current `main`, **When** the term index is built, **Then** it contains an active `activation ledger` term whose definition names `.kittify/charter/activation.yaml`.
2. **Given** the same glossary, **When** a reader opens `active charter`, **Then** the definition names the activation ledger and the `deactivated_<kind>` exclusions, and states that a project not yet upgraded to 4.0.0rc8 keeps the allow keys in the legacy location.

---

### User Story 2 — The core repository keeps seed and pack in parity (Priority: P2)

A maintainer lands the glossary change without editing the fetched `packs/built-in` tree: the entries are authored in `spec-kitty-open-packs`, the core pin is bumped, and the seed mirrors the pack byte-for-byte.

**Why this priority**: The parity gate is a standing invariant; a seed-only edit would fail it. The pack is the consumer-facing copy, the seed drives the published glossary page.

**Independent Test**: `uv run --frozen pytest -q tests/architectural/test_glossary_pack_parity.py` passes after `make sync-packs` at the new pin.

**Acceptance Scenarios**:

1. **Given** the open-packs commit carrying both entries, **When** the core pin is bumped and `make sync-packs` runs, **Then** the seed and pack agree on every seed-present field.
2. **Given** a seed-only edit, **When** the parity test runs, **Then** it fails (the red half of the proof).

---

### User Story 3 — A code reader reaches the glossary from the activation seam (Priority: P3)

A contributor reading `src/charter/activation/activation_ledger.py` or the `ActiveCharterService` module sees a pointer to the canonical glossary entry.

**Why this priority**: The code docstrings name both concepts; a pointer keeps the docs and code vocabulary joined without duplicating the definition.

**Independent Test**: Both module docstrings contain the `docs/context/charter.md` anchor for their concept.

**Acceptance Scenarios**:

1. **Given** `activation_ledger.py`, **When** a reader opens its module docstring, **Then** it links `docs/context/charter.md#activation-ledger`.
2. **Given** `resolver.py`, **When** a reader opens the `ActiveCharterService` module docstring, **Then** it links `docs/context/charter.md#active-charter`.

### Edge Cases

- A project not yet upgraded to 4.0.0rc8 still keeps the allow keys in `.kittify/config.yaml` or the `charter.yaml` it points to; the updated `active charter` entry must say so and must not claim the ledger always exists.
- The new term must not be confused with the Migration Ledger (`.kittify/migration-ledger.jsonl`) or the Decision-Moment ledger.
- A glossary term added to the pack changes no runtime behaviour; no code path may start reading the definition.
- The published glossary page is generated at docs-build time, so the seed is the only checked-in input that must change.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Add the `activation ledger` term | As an operator, I want the glossary to define the activation ledger so that I can recognise `.kittify/charter/activation.yaml` and know it is the single activation authority. | High | Open | [build] | no |
| FR-002 | Update the `active charter` term | As an operator, I want `active charter` to name the ledger and the exclusions so that the entry no longer describes the pre-#6496 location as current. | High | Open | [build] | no |
| FR-003 | Mirror both entries into the built-in glossary pack | As a consumer, I want the shipped built-in pack to carry the same two entries so that projects and the published glossary read the same definitions. | High | Open | [build] | no |
| FR-004 | Re-pin the built-in pack in core | As a maintainer, I want `packs/built-in.source.yaml` to point at the open-packs commit that carries the entries so that `make sync-packs` fetches them and the parity gate passes. | High | Open | [build] | no |
| FR-005 | Link the terms from the activation docstrings | As a contributor, I want the activation ledger and `ActiveCharterService` module docstrings to point at their glossary entries so that code vocabulary and docs stay joined. | Medium | Open | [build] | no |
| FR-006 | Fix the stale guide location | As an operator reading the governance troubleshooting guide, I want `charter activate --preset` described as writing the activation ledger, not `.kittify/config.yaml`, so that the guide is true after #6496. | Medium | Open | [build] | no |
| FR-007 | Pass the docs freshness gates | As a maintainer, I want the docs index, ADR inventory and freshness gates to stay at errors=0 after the doc edits so that the PR is mergeable. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Seed/pack parity | `tests/architectural/test_glossary_pack_parity.py` passes with 0 mismatched seed-present fields after `make sync-packs` at the new pin. | Correctness | High | Open |
| NFR-002 | Glossary readability | Both definitions pass the `kitty-glossary-writing` bar: one concept per definition, no circular wording, no source paths or issue numbers in the definition body, and the "not the Migration Ledger" distinction is explicit. | Usability | High | Open |
| NFR-003 | Docs freshness | `scripts.docs.check_docs_freshness --ci` reports errors=0 and `tests/architectural/test_no_legacy_terminology.py` stays green. | Reliability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Change pack content upstream | The entries are authored in `spec-kitty-open-packs`; `packs/built-in/` in this repository is fetched and must not be edited or committed. | Technical | High | Open |
| C-002 | No behavioural code change | The change is documentation and data only; no CLI, runtime or activation logic may change. | Technical | High | Open |
| C-003 | Definitions cite the canonical docs and ADRs | The definition prose cites the `docs/context/charter.md` entry and ADR `2026-10-19-1`, not source paths or issue numbers (shrink-only provenance style). | Technical | Medium | Open |
| C-004 | Preserve the red-first proof | The new glossary regression test must be observed failing on the pre-change tree before the definitions are applied. | Process | High | Open |

### Key Entities

- **Activation ledger**: the git-tracked `.kittify/charter/activation.yaml`; holds `activated_kinds`, `mission_type_activations`, the three-state `activated_<kind>` allow state and the `deactivated_<kind>` exclusions.
- **Active charter**: the project's activated set as a whole — the allow state minus exclusions — stored in the activation ledger; not the `.kittify/charter/` tree.
- **Built-in glossary pack**: `spec-kitty-core`, the consumer-shipped term set; mirrored byte-for-byte by the core seed.
- **Glossary seed**: `.kittify/glossaries/spec_kitty_core.yaml`, the checked-in input to the published glossary page and the parity gate.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The seed and the built-in pack each carry an active `activation ledger` term with confidence ≥ 0.9 whose definition names `.kittify/charter/activation.yaml`, and their `active charter` definitions name the ledger — [build] · no-op passable: no
- **SC-002**: The focused glossary regression test fails on the pre-change tree and passes after the change; the standing parity test passes at the new pin — [build] · no-op passable: no
- **SC-003**: `docs_index`, `freshen_adr_inventory --check`, `check_docs_freshness --ci` (errors=0) and the no-legacy-terminology test are green on the PR head — [build] · no-op passable: no
- **SC-004**: the two module docstrings link their concept to `docs/context/charter.md` — [build] · no-op passable: no
