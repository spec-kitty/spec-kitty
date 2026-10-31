# Mission Specification: Glossary entry for the three "residue" senses

**Mission Branch**: `issue-6759-glossary-residue`
**Created**: 2026-10-30
**Status**: Draft
**Input**: Issue spec-kitty/spec-kitty#6759 — 'Glossary: "residue" now has three meanings and no docs/context entry'. Follow-up from the pre-merge squad on #5875.

## Mission Boundary

"Residue" — a `kitty-specs/` child that is not a Mission — has three live,
independently justified definitions in code, each with its own docstring, and no
`docs/context/` glossary entry. This is the same footgun class as `primary`,
`merge` and `routing` (Terminology Canon, AGENTS.md). The mission adds the
glossary entry and links it from the three owning docstrings. It is a
docs-plus-docstrings change with a structural red-first test; **no runtime
behavior changes**.

The three senses, per the issue and the code on `main`@512567ee:

1. **Write-seam residue** — `is_kitty_specs_residue`
   (`src/specify_cli/context/mission_resolver.py`, #6627/#6668/#6680): whether a
   write seam (upgrade sweep, migration runner) must leave a `kitty-specs/`
   child untouched. A `spec.md` on disk keeps a folder out of residue, so the
   upgrade sweep can still repair it.
2. **Audit-engine residue** — `RESIDUE_DIRECTORY`
   (`src/specify_cli/audit/models.py`, engine `src/specify_cli/audit/engine.py`,
   #5812): a directory that is not a Mission per `is_mission_dir`, reported as
   one INFO finding and not classified (the engine keeps this looser rule
   deliberately: `mission-walker-residue-rule-01M5ZC0X#FR-008`, issue #5875).
3. **Read-side / `doctor identity` residue** — `not is_selectable_mission_dir`
   (`src/specify_cli/context/mission_resolver.py`,
   `src/specify_cli/status/identity_audit.py`, #5875 operator ruling 2026-10-27):
   covers no `meta.json` on disk; an untracked id-less `meta.json` in a git
   repository; an unreadable `meta.json`. Mission selection never lists these
   folders.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A reader can disambiguate "residue" from the glossary (Priority: P1)

A maintainer or agent reader who encounters "residue" in a docstring, an issue or
a review opens `docs/context/` and finds one entry that names the three live
senses, each with its owning code symbol, its rule, and a "do NOT use when"
guard steering to the neighboring sense — the same shape as the existing
`primary`/`merge`/`routing` entries.

**Why this priority**: The issue's core ask; without the entry the footgun stays.

**Independent Test**: `docs/context/orchestration.md` carries a `### Residue`
entry naming all three senses with guards; a structural test asserts this.

**Acceptance Scenarios**:

1. **Given** `docs/context/orchestration.md`, **When** the reader looks for the
   residue disambiguation, **Then** a `### Residue` term entry exists with
   Definition / Context / Status / Applicable to rows, a "Do NOT use when" row
   per the glossary-conventions schema, and it names the senses "write-seam
   residue", "audit-engine residue" and "read-side residue" with their owning
   symbols (`is_kitty_specs_residue`, `RESIDUE_DIRECTORY`,
   `is_selectable_mission_dir`).
2. **Given** the entry, **When** the reader follows an owning symbol, **Then**
   each of the three sense definitions matches the code's actual rule (a
   `spec.md` on disk keeps a folder out of write-seam residue; the audit engine
   keeps `not is_mission_dir`; selection uses `not is_selectable_mission_dir`).

### User Story 2 - The three docstrings point at the entry (Priority: P2)

A reader in the code — where the term is actually overloaded — lands on one of
the three docstrings and finds a link to the glossary entry, so the local
justification and the cross-codebase disambiguation are one hop apart.

**Why this priority**: Without the links the entry exists but is undiscoverable
from the code, which is where the confusion bites (each docstring is
individually justified and correct).

**Independent Test**: The three owning docstrings each reference
`docs/context/orchestration.md#residue`.

**Acceptance Scenarios**:

1. **Given** `is_kitty_specs_residue` in `src/specify_cli/context/mission_resolver.py`,
   **When** its docstring is read, **Then** it links the glossary entry.
2. **Given** `RESIDUE_DIRECTORY` in `src/specify_cli/audit/models.py`, **When**
   its docstring comment is read, **Then** it links the glossary entry.
3. **Given** `is_selectable_mission_dir` in
   `src/specify_cli/context/mission_resolver.py`, **When** its docstring is
   read, **Then** it links the glossary entry.

### User Story 3 - The disambiguation is discoverable from the Terminology Canon (Priority: P3)

A reader of AGENTS.md's Terminology Canon (where `primary`, `merge` and
`routing` footguns are flagged) is told "residue" is overloaded and pointed at
the entry.

**Why this priority**: Consistency with the established footgun pattern; one
sentence, no new authority (the glossary stays the single authority).

**Independent Test**: AGENTS.md Terminology Canon carries a residue bullet
linking the glossary anchor.

**Acceptance Scenarios**:

1. **Given** AGENTS.md's Terminology Canon section, **When** the reader scans
   the overloaded-term bullets, **Then** a residue bullet names the three senses
   in one line and links `docs/context/orchestration.md#residue`.

### Edge Cases

- The glossary entry must not silently restate any rule as new authority: it
  links the owning code symbols and the #5875/#5812/#6627 provenance; code stays
  the source of truth (docs-freshness doctrine).
- Adding a term to `orchestration.md` (a Contextive-mapped context) must
  regenerate the committed generated file
  `src/specify_cli/.contextive/orchestration.yml`
  (`scripts/generate_contextive_glossaries.py generate`), keeping its `check`
  mode green.
- The docstring links must use the relative-docs form already used in `src/`
  docstrings (e.g. ``docs/context/orchestration.md#residue``), matching
  `src/specify_cli/state/contract.py`.
- The structural test must not pin prose wording (it fights every future edit);
  it pins presence, sense names, guards and links, modeled on
  `tests/docs/test_artifact_placement_seam_page.py`'s Routing disambiguation
  test.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Residue glossary entry | As a glossary reader, I want one `docs/context/` entry for "residue" naming its three live senses with "do NOT use when" guards, so I can tell which sense a docstring or issue means. | High | Open | [build] | no — a structural test asserts the entry, the three sense names and the guards |
| FR-002 | Docstring links | As a code reader, I want each of the three owning docstrings (`is_kitty_specs_residue`, `RESIDUE_DIRECTORY`, `is_selectable_mission_dir`) to link the glossary entry, so the local rule and the disambiguation are one hop apart. | High | Open | [build] | no — the structural test asserts each docstring references the entry anchor |
| FR-003 | Terminology Canon bullet | As an AGENTS.md reader, I want the Terminology Canon to flag "residue" as an overloaded term linking the entry, so the footgun is visible where the sibling footguns are. | Medium | Open | [build] | no — the structural test asserts the canon bullet links the anchor |
| FR-004 | Generated Contextive file regenerated | As an IDE user, I want `src/specify_cli/.contextive/orchestration.yml` regenerated to include the new term, so the hover glossary stays in sync with the canonical markdown. | Medium | Open | [folded] — satisfied by running the generator after FR-001 | yes — regeneration is mechanical; pinned by the generator's own check mode |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|--------|--------|
| NFR-001 | Entry follows the glossary styleguide | The entry follows `styleguide:kitty-glossary-writing` and the per-term schema in `docs/context/glossary-conventions.md` (Definition / Context / Status / Applicable to / Do NOT use when rows); definitions are functional, clear, and HiC-consistent. | Quality | High | Open |
| NFR-002 | No behavior change | Zero runtime behavior change: only markdown, docstrings (comments) and generated glossary YAML change; no `src/` logic, no CLI surface. The full targeted test surface passes. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|--------|--------|
| C-001 | Code is the source of truth | The entry documents shipped behavior and cites the owning symbols; it must not introduce a second authority for any residue rule. | Technical | High | Open |
| C-002 | Docs gates | The docs gates pass after the change: `docs_index --write` (if the index changes), `freshen_adr_inventory`, `check_docs_freshness --ci` (errors=0) and `tests/architectural/test_no_legacy_terminology.py`. | Technical | High | Open |
| C-003 | Smallest viable diff | Per `change-apply-smallest-viable-diff`: one glossary entry, three docstring links, one canon bullet, the regenerated YAML, one test file, changelog entry; no unrelated doc rewrites. | Technical | Medium | Open |

### Key Entities

- **Residue (term surface)**: one word, three term senses, each owned by a code
  symbol and a provenance issue (#6627/#6668/#6680, #5812, #5875).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `docs/context/orchestration.md` carries a `### Residue` entry naming the senses "write-seam residue", "audit-engine residue" and "read-side residue", each with a "do NOT use when" guard — [build] · no-op passable: no
- **SC-002**: Each of the three owning docstrings references `docs/context/orchestration.md#residue` — [build] · no-op passable: no
- **SC-003**: A red-first structural test in `tests/docs/` pins SC-001 and SC-002 (and the AGENTS.md canon link), and is red on the planning base before the change and green after — [build] · no-op passable: no
- **SC-004**: `python scripts/generate_contextive_glossaries.py check` exits 0 after the change — [ratchet] · no-op passable: no
