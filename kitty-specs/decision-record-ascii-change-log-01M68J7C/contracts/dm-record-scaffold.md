# Contract: Decision Moment record scaffold is byte-safe

**Mission**: `decision-record-ascii-change-log-01M68J7C` (issue #6579)
**Owner**: `src/specify_cli/decisions/store.py` (the sole renderer of `DM-<ulid>.md`)
**Status**: enforced by `tests/specify_cli/decisions/test_store.py`

## Scope

This contract covers the **generated scaffold** of a Decision Moment record: the title, metadata
bullets, section headings, and the `## Change log` entries. It does not cover user-authored field
values, which are rendered verbatim.

## Invariants

1. **ASCII scaffold.** For an `IndexEntry` whose user-authored fields are ASCII (`question`,
   `options`, `rationale`, `final_answer`, `resolved_by`, keys, ids), the bytes written by
   `write_artifact` satisfy `max(path.read_bytes()) <= 0x7F`. Every lifecycle status is covered:
   `open`, and the terminal `resolved` / `deferred` / `canceled` with and without `final_answer`.
2. **Gate-clean.** The same record yields `detect_problematic_characters(text) == []` from
   `specify_cli.text_sanitization`, the detector behind `spec-kitty validate-encoding`. A mission
   that opens a Decision Moment therefore passes its own encoding gate without a `--fix` pass.
3. **Authored content is untouched.** A non-ASCII character in a user-authored field survives the
   round trip verbatim, and the encoding gate still flags it. The writer never transliterates a
   maintainer's prose; the strict gate remains the signal for author content.
4. **One separator authority.** The change-log bullet separator is a single module-level ASCII
   constant (`store._CHANGE_LOG_SEPARATOR`), used by both the "opened" and terminal bullets, so the
   invariant has one home and one test.

## What is explicitly not constrained

- The record's field order, headings and section list (the existing tests pin those separately) and
  the `(final_answer="...")` suffix shape.
- The `validate-encoding` command, its mapping table and its exit codes: this contract is satisfied
  by the writer, never by relaxing the gate.

## Verification

`pytest tests/specify_cli/decisions/test_store.py -k "ascii or verbatim"` — the byte-safe pin and the
authored-content preservation pin, both in `TestWriteArtifact`.
