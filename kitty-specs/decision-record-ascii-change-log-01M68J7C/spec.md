# Mission Specification: Decision records are written byte-safe (ASCII change log)

**Mission Branch**: `kitty/mission-decision-record-ascii-change-log-01M68J7C`
**Created**: 2026-10-31
**Status**: Draft
**Input**: User description: "Issue spec-kitty/spec-kitty#6579 — fix(decisions): decision records are written with a literal U+2014 em dash, so validate-encoding fails"

## Summary

`specify_cli.decisions.store._render_artifact` renders the Decision Moment (DM) record's
`## Change log` bullets with a literal U+2014 em dash:

```python
lines.append(f"- `{entry.created_at.isoformat()}` — opened")
lines.append(f"- `{entry.resolved_at.isoformat()}` — {entry.status.value}")
```

Every mission that opens a Decision Moment therefore writes a `kitty-specs/<slug>/decisions/DM-*.md`
artifact whose bytes are not ASCII, and `spec-kitty validate-encoding --mission <slug>` refuses it
(FR-003 of `text_sanitization`, observed on `fork-hardening-01M5DTVE`: 4 U+2014 codepoints across two
DM files). The validator's `--fix` can transliterate the bytes after the fact, but the writer must be
byte-safe by construction so no mission has to run a repair pass over an artifact the tool itself wrote.

The fix belongs in the writer, not the validator: the DM record is a generated file under
`kitty-specs/`, and generated markdown/JSON/YAML in this repository must stay byte-safe ASCII so the
strict encoding gate stays meaningful for author-written content.

## Grounding

- Reproduced on `main` at `35318ef51c` by rendering a resolved `IndexEntry` through the pre-existing
  public writer `specify_cli.decisions.store.write_artifact`: the artifact contains 6 non-ASCII bytes
  (two U+2014 sequences) on the two `## Change log` lines, `max(byte) == 0xE2`.
- Introduced in `e07e9439d2` (Decision Moment V1) and never touched since; `git log -S` over
  `store.py` finds no later change to the bullet, and no `[Unreleased]` changelog entry mentions it.
- `store.py::_render_artifact` is the only renderer of DM markdown: `emit.py` writes JSONL events,
  `fork.py`/`verify.py`/`index_fold.py`/`service.py` write or read index/artifact state through
  `store.py`. There is no template that mirrors the same bullet.
- Not superseded: no open PR or merged commit on `main` addresses #6579 (issue is unassigned and
  uncommented apart from this Mission's claim).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A mission that opens a Decision Moment passes its own encoding gate (Priority: P1)

A maintainer runs a mission, the runtime opens (and later resolves) a Decision Moment, and the mission
tree is validated with `spec-kitty validate-encoding --mission <slug>`. Today the gate refuses the DM
artifact the tool just wrote. After the fix, the record's fixed scaffold is ASCII and the gate passes
without a repair pass.

**Why this priority**: this is the reported defect; without it every mission with a Decision Moment
inherits a spurious gate red that a maintainer must repair by hand.

**Independent Test**: write a DM record through `write_artifact` for an open entry and for a resolved
entry, then run the encoding detector / `validate-encoding` over the mission's `decisions/` directory
and confirm it is clean.

**Acceptance Scenarios**:

1. **Given** a resolved `IndexEntry` whose user-supplied fields are ASCII, **When** `write_artifact`
   writes `DM-<id>.md`, **Then** every byte of the file is `< 0x80` and
   `specify_cli.text_sanitization.detect_problematic_characters` reports no issue.
2. **Given** an open `IndexEntry`, **When** `write_artifact` writes the record, **Then** the
   `## Change log` "opened" bullet is ASCII and the file is byte-safe.
3. **Given** a `deferred` or `canceled` entry, **When** the record is written, **Then** the terminal
   bullet (with and without `final_answer`) is ASCII and the file is byte-safe.

### User Story 2 - The invariant is pinned against regression (Priority: P2)

A contributor changing the DM renderer cannot reintroduce a non-ASCII glyph without a failing test.

**Why this priority**: the glyph arrived with the original feature and survived every later change to
the module; only a pin keeps it out.

**Independent Test**: the new regression test fails on `main` before the fix and passes after it.

**Acceptance Scenarios**:

1. **Given** the pre-fix renderer, **When** the new test runs, **Then** it fails on the U+2014 byte.
2. **Given** the fixed renderer, **When** the decisions test module runs, **Then** it passes and no
   existing store/service/CLI decision test changes behavior.

### Edge Cases

- A DM record whose *user-authored* fields (question, options, rationale, final_answer) legitimately
  contain non-ASCII prose: the writer must not silently rewrite content; only the fixed scaffold is
  guaranteed ASCII. `validate-encoding` still owns user content.
- The `## Change log` for an entry that was opened, resolved and then re-rendered after an update
  (`update_entry` + `write_artifact`) must stay ASCII in every terminal status branch.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | ASCII change-log bullets | As a maintainer, I want DM change-log bullets rendered with ASCII only so that a written record is byte-safe. | High | Open | [build] | no |
| FR-002 | Writer-side fix, not validator-side | As a maintainer, I want the writer fixed and the encoding gate untouched so that the gate keeps refusing genuinely non-ASCII author content. | High | Open | [build] | no |
| FR-003 | Record scaffold is byte-safe for every status | As a maintainer, I want a DM record whose ASCII inputs produce an all-ASCII file for open, resolved, deferred and canceled entries with and without `final_answer`. | High | Open | [build] | no |
| FR-004 | Sole-renderer sweep | As a maintainer, I want the decisions package checked for any other render path that mirrors the same bullet, so the fix has one home. | Medium | Open | [build] | no |
| FR-005 | Regression pin | As a contributor, I want a test through `write_artifact` that fails on the em dash and passes on ASCII so the glyph cannot return. | High | Open | [ratchet] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Byte threshold | For an entry whose user fields are ASCII, a written DM record contains zero bytes `>= 0x80`; measured as `max(path.read_bytes()) <= 0x7F`. | Correctness | High | Open |
| NFR-002 | Fast test cost | The new pin runs in the unit/fast lane and adds under 0.1 s to `tests/specify_cli/decisions`. | Performance | Medium | Open |
| NFR-003 | No behavioral drift | Existing DM record headings, field order and change-log line shape stay stable apart from the separator glyph; all pre-existing decisions tests pass unchanged. | Compatibility | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Gate unchanged | `validate_encoding` / `text_sanitization.PROBLEMATIC_CHARS` are not modified, relaxed or bypassed. | Technical | High | Open |
| C-002 | No content rewriting | User-authored field values are rendered verbatim; the mission does not strip or transliterate author prose. | Technical | High | Open |
| C-003 | Locality | The change stays inside `src/specify_cli/decisions/store.py` plus its tests, changelog and docs. | Technical | Medium | Open |

### Key Entities

- **Decision record artifact** (`kitty-specs/<slug>/decisions/DM-<decision_id>.md`): generated markdown,
  rendered by `_render_artifact` and written atomically by `write_artifact`.
- **IndexEntry**: the ledger row supplying the fields rendered into the record (status, timestamps,
  question, options, final answer, rationale).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For an ASCII-input entry in each status, a written DM record's maximum byte is `<= 0x7F` — [build] · no-op passable: no
- **SC-002**: `detect_problematic_characters` over a writer-produced resolved record reports zero issues — [build] · no-op passable: no
- **SC-003**: The new pin fails on the pre-fix renderer and passes on the fixed one, proven by running it both ways — [ratchet] · no-op passable: no
- **SC-004**: The whole `tests/specify_cli/decisions` module suite and the existing `validate-encoding` tests stay green — [ratchet] · no-op passable: no

## Out of Scope

- Repairing existing mission artifacts that already contain the glyph (`validate-encoding --fix` owns that).
- Changing the `validate-encoding` command, its mapping table or its exit codes.
- Rendering or validating user-authored prose content.
