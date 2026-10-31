# Mission Specification: Contract Scenario glossary entry and the Pack Level "tier" wording

**Mission Branch**: `issue-6439-contract-scenario-glossary-and-pack-level`
**Created**: 2026-10-31
**Status**: Draft
**Input**: Issue #6439 — "Glossary: add 'Contract Scenario'; Pack Level entry says 'tier'"

## Intent Summary

- **Primary actor**: a contributor or maintainer who meets the word *contract scenario*
  (in `spec-kitty-charter`, or in a conformance discussion) and looks it up in Spec
  Kitty's glossary, and the same reader who looks up *Pack Level*.
- **Trigger**: the reader consults `docs/context/` for either term. Today *Contract
  Scenario* is absent, and *Pack Level* calls a pack's level a "tier", which the
  downstream domain language forbids.
- **Outcome**: `docs/context/` defines **Contract Scenario** beside Charter Pack, with
  its home, related terms and a `Do NOT use when` guard, and the **Pack Level** entry
  says a pack's *level* — a level token, not a tier token — throughout.
- **Invariant**: `docs/context/` stays the single source of truth for glossary wording;
  `kernel.pack_tiers` (a module name) and the separate **Organization Tier** term are
  unchanged, so the change is prose only.
- **Canonical terms**: "Contract Scenario" (never bare "scenario", never "BDD
  scenario"); "level" for what a pack declares, "layer" for a merged-graph layer;
  "tier" is not used for a pack's level in the entries this mission touches.

Confirmation: this run is a delegated sub-agent with no live user. The operator's
standing brief stands in for the interview; its decisions are recorded as Decision
Moments.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Look up "Contract Scenario" and find it defined (Priority: P1)

A contributor reading the contract half of the charter (`contracts/charter/scenarios/`,
the `@contract` / `@provisional` tags) looks the term up in Spec Kitty's glossary
instead of inferring it from the downstream repository.

**Why this priority**: this is the whole point of the issue. `spec-kitty-charter`
imports this glossary verbatim and cannot add the term locally, so if the entry does
not live here it does not exist anywhere.

**Independent Test**: read `docs/context/charter.md` and find a `### Contract Scenario`
entry carrying the definition, home, related terms and do-not-use-when the issue
proposes.

**Acceptance Scenarios**:

1. **Given** the core glossary, **When** a reader looks up "Contract Scenario", **Then**
   the entry says it is the Gherkin behavior half of the charter contract, naming pack
   files, calling one operation of `contracts/charter/openapi.yaml` and stating the
   answer.
2. **Given** the same entry, **When** the reader follows its related-terms row, **Then**
   it reaches *Charter Pack* (in the same page) and names *Acceptance Scenario* and
   *Conformance Corpus* as the terms it is not.
3. **Given** a reader who means the BDD practice or the acceptance scenarios, **When**
   they read the `Do NOT use when` row, **Then** it steers them away from "BDD
   scenarios" and to the neighbouring terms.

---

### User Story 2 - Pack Level stops calling a pack's level a "tier" (Priority: P2)

A reader of the **Pack Level** entry learns that a pack declares a *level*, matching
the downstream rule that a pack has a level and the merged graph has layers, never a
"tier".

**Why this priority**: the imported entry currently contradicts the consuming
repository's own domain language, so a downstream reader is told two different things
about the same word.

**Independent Test**: read the **Pack Level** entry; no prose calls a pack's level a
"tier", and `kernel.pack_tiers` is still named as the one authority.

**Acceptance Scenarios**:

1. **Given** the **Pack Level** entry, **When** its definition is read, **Then** it
   opens with the *level* a Charter Pack declares, by the `pack_level` field in its
   `pack.yaml`, and says "level token", not "tier token".
2. **Given** the same entry, **When** the `PACK_LEVEL_MISMATCH` / `PACK_LEVEL_MISSING`
   / deprecation-window clauses are read, **Then** they are unchanged apart from the
   wording, and `kernel.pack_tiers` is still the one authority for the level names.
3. **Given** the **Charter Pack** entry, which restates the same claim ("the tier
   token"), **When** it is read, **Then** it also says "level token", so the glossary
   does not contradict itself two entries apart.

---

### User Story 3 - The correction cannot silently regress (Priority: P2)

A maintainer changes the glossary later and a standing test tells them if the word
"tier" returns to either entry or the new term loses a required row.

**Why this priority**: a docs correction with no guard regrows; the repository already
pins glossary entries this way (`test_glossary_authority_parity` asserts the
`Do NOT use when` row on `charter`).

**Independent Test**: run the new docs test; it fails on the pre-fix tree and passes
after the fix.

**Acceptance Scenarios**:

1. **Given** the pre-fix `docs/context/governance.md`, **When** the new test runs,
   **Then** it fails naming the "tier" wording in the Pack Level entry.
2. **Given** the pre-fix `docs/context/charter.md`, **When** the new test runs,
   **Then** it fails naming the missing `### Contract Scenario` entry.
3. **Given** the fixed tree, **When** the same test runs, **Then** it passes, and it
   still passes when the only change is `kernel.pack_tiers` in a code span.

---

### Edge Cases

- `kernel.pack_tiers` is a module name and stays. Any check for the word "tier" must
  ignore inline code spans, or it would red on the authority name it is protecting.
- The **Organization Tier** term (and the *Three-layer DRG* entry's "three-tier"
  prose) is a different sense of the word, owned by a separate rename. This mission
  must not rename it, and the guard must not assert its absence.
- A `docs/context/` entry is markdown table rows: the definition must stay one cell,
  keep every required row (`Definition`, `Context`, `Status`, `Applicable to`), and
  keep the page's existing frontmatter and heading level.
- The downstream repository re-imports this glossary verbatim; the entry must not
  cite this repository's issue numbers or `src/` paths in prose.
- `Applicable to` for Contract Scenario: the charter contract is a 4.x concern, but
  the entry describes a term, not a behaviour gate — the neighbouring Charter Pack
  entry uses `4.x`, so the new entry matches it.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Add the Contract Scenario entry | As a reader, I want a **Contract Scenario** entry in `docs/context/charter.md` beside Charter Pack, carrying the issue's definition, home, related terms and `Do NOT use when` guard, so that the term resolves in core and, through the import, downstream. | High | Open | [build] | no — the tree has no such entry today (the test names it as missing) |
| FR-002 | Pack Level says level, not tier | As a reader, I want the **Pack Level** entry in `docs/context/governance.md` to open with the level a pack declares and to say "level token", so that core's glossary agrees with the downstream rule that a pack has a level and the graph has layers. | High | Open | [build] | no — the pre-fix entry opens "The tier a Charter Pack occupies" |
| FR-003 | Charter Pack's restatement matches | As a reader, I want the **Charter Pack** entry's "the tier token" to read "the level token", so that the one claim is not stated two ways two entries apart. | Medium | Open | [build] | no — the phrase is present verbatim in the pre-fix entry |
| FR-004 | The correction is pinned by a test | As a maintainer, I want a standing docs test that fails on the pre-fix tree for both halves and passes after, ignoring `kernel.pack_tiers` in code spans, so that the wording cannot silently return. | High | Open | [ratchet] | no — paired with the same-fixture positive control that the probe sees the required rows when present |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Docs gates stay green | `docs_index`, `freshen_adr_inventory --check`, `check_docs_freshness --ci` (errors=0) and `tests/architectural/test_no_legacy_terminology.py` all pass with zero errors on the mission head, with no gate skipped or weakened. | Quality | High | Open |
| NFR-002 | Styleguide conformance | Every new or edited entry follows `styleguide:kitty-glossary-writing`: one concept per definition, no buzzword soup, functional over compositional, no "user" where Human-in-Charge (HiC) holds decision authority, and a definition a newcomer can read without a follow-up question. | Documentation | High | Open |
| NFR-003 | Bounded diff | The mission edits only `docs/context/charter.md`, `docs/context/governance.md`, one new test module under `tests/docs/`, and one `docs/changelog/CHANGELOG.md` entry. `kernel.pack_tiers`, the Organization Tier term and every generated surface are untouched. | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | `docs/context/` is the only glossary source | The entry is authored in `docs/context/`, the doctrine-extraction source; it is not added to the seed, the built-in pack, or a generated site file. | Technical | High | Open |
| C-002 | No gate may be weakened | No skip, xfail, allowlist entry or baseline addition. A red that is not attributable to this diff is cited in `## Deferred`, not suppressed. | Process | High | Open |
| C-003 | Out-of-scope terms are untouched | *Organization Tier*, the *Three-layer DRG* entry's "three-tier" prose and `kernel.pack_tiers` keep their wording; the issue's `PACK_LEVEL_MISSING` clause (#6403) is already shipped and is not re-litigated. | Business | High | Open |

### Key Entities *(include if the mission involves data)*

- **Glossary entry**: a `### Term` heading followed by a two-column markdown table whose
  required rows are `Definition`, `Context`, `Status` and `Applicable to`, with optional
  `Do NOT use when` / `Related terms` rows (`docs/context/glossary-conventions.md`).
- **Terms referenced by the new entry**: Charter Pack, Acceptance Scenario, Conformance
  Corpus, `contracts/charter/openapi.yaml`, `contracts/charter/scenarios/`, `@contract`,
  `@provisional`, `verifyAll`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The core glossary defines **Contract Scenario** with the definition, home, related terms and `Do NOT use when` guard the issue proposes; a reader finds it in `docs/context/charter.md` beside Charter Pack — [build] · no-op passable: no
- **SC-002**: Neither the **Pack Level** entry nor the **Charter Pack** entry calls a pack's level a "tier" in prose (zero occurrences outside inline code spans), while `kernel.pack_tiers` is still named — [build] · no-op passable: no
- **SC-003**: One new test module fails on the pre-fix tree for both halves (four failing assertions: missing entry, missing rows, "tier" in Pack Level, "tier" in Charter Pack) and passes on the fixed tree — [ratchet] · no-op passable: no
- **SC-004**: The docs gates named in NFR-001 report zero errors on the mission head — [ratchet] · no-op passable: no
