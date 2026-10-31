# Tasks: Decision records are written byte-safe (ASCII change log)

**Mission**: `decision-record-ascii-change-log-01M68J7C`
**Spec**: [spec.md](./spec.md) · **Plan**: [plan.md](./plan.md)
**Issue**: spec-kitty/spec-kitty#6579

## Overview

One defect, one renderer, one pin. `store._render_artifact` is the only producer of Decision Moment
markdown, so the whole mission is a single sequential work package: prove the em dash red through the
public `write_artifact`, replace the glyph with an ASCII separator in that renderer, then prove the
same test green and the surrounding suites unchanged. Splitting the fix from its pin would only
create an artificial red commit on a lane.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Survey `src/specify_cli/decisions/` for every DM markdown render path; confirm `store._render_artifact` is the sole producer of the `## Change log` bullet (FR-004) | WP01 | |
| T002 | Red-first pin `test_artifact_is_ascii_for_every_status` driven through `write_artifact`, asserted on file bytes and the gate's own detector (FR-005) | WP01 | |
| T003 | Fix the writer with one ASCII separator constant used by both change-log bullets; validator untouched (FR-001, FR-002, FR-003) | WP01 | |
| T004 | Green plus blast radius: decisions suite, `validate-encoding` command tests, ruff/format/mypy on touched files (SC-004) | WP01 | |

## Work Packages

### WP01 — Render the DM change log with an ASCII separator and pin the byte-safe invariant

**Goal**: A Decision Moment record written by `write_artifact` is ASCII for ASCII inputs in every
status, so `spec-kitty validate-encoding --mission <slug>` accepts the artifact the tool itself
wrote, and a regression test refuses any reintroduced non-ASCII glyph in the record scaffold.

**Priority**: P1 (#6579; every mission that opens a Decision Moment inherits a gate red today).

**Independent test**: `pytest tests/specify_cli/decisions/test_store.py -k ascii` — fails on the
pre-fix renderer (`0xE2` on the change-log lines), passes after T003 with no other assertion changed.

**Included subtasks**:

T001 Survey the decisions package for render paths (WP01)
T002 Write the red-first ASCII pin through `write_artifact` (WP01)
T003 Replace the em dash with an ASCII separator constant in the renderer (WP01)
T004 Verify green, blast radius and static checks (WP01)

**Implementation sketch**:
1. **T001 survey** — read `store.py`, `emit.py`, `service.py`, `fork.py`, `verify.py`,
   `index_fold.py`; the change-log bullet appears only in `store._render_artifact`. Record the
   finding in `traces/approach.md`.
2. **T002 red** — add the pin to the existing `TestWriteArtifact` class; run it and capture the
   failure (6 non-ASCII bytes, two U+2014 sequences, `max byte 0xE2`). Record the red output in
   `traces/design-decisions.md`.
3. **T003 fix** — introduce `_CHANGE_LOG_SEPARATOR` with the "ASCII only, generated file" comment
   and use it in both bullets, keeping the `(final_answer="...")` suffix.
4. **T004 verify** — pin green, `pytest tests/specify_cli/decisions`, the `validate-encoding` command
   tests, `ruff check`/`ruff format --check`/`mypy` on the two touched files.

**Parallel opportunities**: none — the pin and the fix touch the same behaviour in sequence.

**Dependencies**: none.

**Requirement refs**: FR-001, FR-002, FR-003, FR-004, FR-005, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, SC-001, SC-002, SC-003, SC-004.

**Risks**: (a) a vacuous pin that only reads the constant back — mitigated by driving
`write_artifact` end to end and asserting on the file's bytes and the gate's own detector; (b) an
accidental wider change to the record layout — mitigated by the unchanged existing heading/field
tests (NFR-003); (c) temptation to "fix" the validator instead — excluded by C-001.

**Prompt**: [tasks/WP01-ascii-change-log.md](./tasks/WP01-ascii-change-log.md)

## MVP scope

WP01 is the entire mission; it is the MVP.
