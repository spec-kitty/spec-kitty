# Implementation Plan: Decision records are written byte-safe (ASCII change log)

**Branch**: `issue-6579-decision-record-ascii` | **Date**: 2026-10-31 | **Spec**:
`kitty-specs/decision-record-ascii-change-log-01M68J7C/spec.md`
**Input**: Mission specification from `kitty-specs/decision-record-ascii-change-log-01M68J7C/spec.md`

## Summary

One writer renders the `## Change log` section of a Decision Moment (DM) record with a literal
U+2014 em dash. Replace the glyph with an ASCII separator in
`src/specify_cli/decisions/store.py::_render_artifact`, keep the encoding validator exactly as it
is, and pin the "a writer-produced record is ASCII" invariant with a regression test that drives the
public `write_artifact` entry point and the gate's own detector.

## Technical Context

**Language/Version**: Python 3.11 (repository `requires-python >= 3.11`; `.python-version` pins 3.11)
**Primary Dependencies**: Pydantic v2 (`IndexEntry` / `DecisionIndex` models), Typer (CLI), pytest (tests); no new dependency
**Storage**: JSON index (`kitty-specs/<slug>/decisions/index.json`) plus per-decision markdown artifacts (`DM-<ulid>.md`) on the primary partition
**Testing**: pytest unit/fast lane (`tests/specify_cli/decisions/test_store.py`) plus the existing `validate-encoding` command tests
**Target Platform**: Linux/macOS developer CLI (cross-platform text I/O; artifact bytes must be UTF-8/ASCII-safe)
**Project Type**: single Python package (`src/specify_cli`) with the repo's layered kernel/runtime seams
**Performance Goals**: no measurable cost; the change replaces a literal with a literal
**Constraints**: `validate_encoding` and `PROBLEMATIC_CHARS` untouched; user-authored field values rendered verbatim
**Scale/Scope**: one renderer function (3 lines), one regression test, changelog entry

## Charter Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **Single canonical authority** — the renderer in `decisions/store.py` is the one authority for DM
  markdown; the fix lands there and nowhere else (no second formatter, no template copy).
- **ATDD-first** — the regression test is written first, through the pre-existing `write_artifact`
  entry point, and observed red on the em dash before the fix.
- **Locality of change (DIRECTIVE_024) / smallest viable diff** — the diff is the separator glyph,
  a short invariant comment, and the pin test; no refactor of the renderer, no validator change.
- **Glossary** — "Decision Moment", "decision record artifact", "primary partition" are used as
  `docs/context/` defines them; no new term is introduced.
- **No gate weakening** — the strict ASCII gate keeps refusing author prose; only the tool's own
  generated scaffold becomes ASCII by construction.

## Project Structure

### Documentation (this mission)

```
kitty-specs/decision-record-ascii-change-log-01M68J7C/
├── plan.md              # This file
├── spec.md              # Mission specification
└── tasks.md             # Work packages (/spec-kitty.tasks)
```

### Source Code (repository root)

```
src/specify_cli/decisions/
├── store.py             # _render_artifact: the only DM markdown renderer (the fix)
└── ...                  # emit.py (JSONL), service.py, models.py, index_fold.py (unchanged)

tests/specify_cli/decisions/
└── test_store.py        # write_artifact suite: the regression pin lands here

docs/changelog/CHANGELOG.md   # [Unreleased] entry
```

**Structure Decision**: single-package change inside the existing `specify_cli.decisions` module and
its owning test module. No new files, no new seams, no API surface change.

## Design

### The change

`store._render_artifact` builds the change log from two `lines.append(f"...")` calls that embed the
em dash. Introduce one module-level constant for the bullet separator and use it in both calls:

```python
# ASCII only: a DM record is a generated file under kitty-specs/ and must pass
# `spec-kitty validate-encoding` (FR-003). Never render U+2014 here (#6579).
_CHANGE_LOG_SEPARATOR = "-"
```

rendering `- \`<timestamp>\` - opened` and `- \`<timestamp>\` - <status>` (with the existing
`(final_answer="...")` suffix). A single named constant gives the invariant one home: a future edit
that changes the separator style has one place to get wrong and one test that catches it.

### Why the writer, not the validator

The gate exists to stop non-ASCII author prose from entering `kitty-specs/`. Its `--fix` pass maps
U+2014 to triple hyphens, so today every DM-opening mission inherits a repair step over a file the
tool itself wrote. Fixing the writer makes the gate meaningful again and leaves the mapping table
(and its behavior on user content) untouched (C-001).

### Why not a general ASCII sanitiser at the write boundary

`IndexEntry` carries user-authored prose (`question`, `options`, `rationale`, `final_answer`). A
blanket transliteration would silently rewrite a maintainer's text (C-002) and hide the real signal
the gate is looking for. The invariant is therefore scoped to the fixed scaffold: for ASCII inputs
the whole file is ASCII (NFR-001).

## Red-first proof

`tests/specify_cli/decisions/test_store.py`, existing `TestWriteArtifact` class:

1. **RED** — `test_artifact_is_ascii_for_every_status` drives `write_artifact` for an `open` entry
   and for `resolved` / `deferred` / `canceled` entries (with and without `final_answer`), then
   asserts `max(path.read_bytes()) <= 0x7F` and that
   `specify_cli.text_sanitization.detect_problematic_characters(text) == []`. On the pre-fix
   renderer this fails with `0xE2` on the change-log lines (reproduced: 6 non-ASCII bytes, two
   U+2014 sequences).
2. **GREEN** — after the separator change the same test passes with no other assertion relaxed.

The detector is the gate's own `detect_problematic_characters`, not a re-implemented character scan,
so the pin tracks the actual refusal path.

## Complexity Tracking

No charter violations. The change needs no new abstraction.

## Implementation Concern Map

### IC-01 — Renderer ASCII invariant

- **Purpose**: Make the DM record's fixed scaffold ASCII by construction, with one named separator
  constant as the invariant's single home.
- **Relevant requirements**: FR-001, FR-002, FR-003, NFR-001, NFR-003, C-001, C-002
- **Affected surfaces**: `src/specify_cli/decisions/store.py`
- **Sequencing/depends-on**: none (IC-02 depends on it)
- **Risks**: the separator must read naturally in a bullet list and must not disturb the
  `(final_answer="...")` suffix; the renderer must stay byte-identical apart from the glyph.

### IC-02 — Regression pin and scope sweep

- **Purpose**: Pin the invariant through the public writer, and prove the decisions package has no
  second render path mirroring the same bullet (FR-004, FR-005).
- **Relevant requirements**: FR-004, FR-005, SC-001, SC-002, SC-003, SC-004
- **Affected surfaces**: `tests/specify_cli/decisions/test_store.py`; read-only sweep of
  `src/specify_cli/decisions/*.py`
- **Sequencing/depends-on**: IC-01
- **Risks**: the pin must be non-vacuous — proven by running it against the pre-fix renderer (RED)
  before applying the fix; a test that only re-reads the constant would pass without the fix.
