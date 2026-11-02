# Design decisions

## D1 — position on `Occurrence`, not a second regex

The label/ref association is lost information, not a bad pattern: `Occurrence` only
kept `line_text`. Adding an optional `ref_offset` keeps the single
`_CONTEXT_MARKER_PATTERN` definition (C-002) and lets the existing arms stay
byte-identical while the *match site* is required to end at the citation.

Rejected: a lookbehind/lookahead regex. It cannot express "12 characters before
*this* `#` but not before an earlier one" without capturing the number, and the
`^`-anchored `see` arm needs the line, not a window.

## D2 — unknown position keeps today's whole-line semantics

External/direct `Occurrence(source_file=…, line_text=…)` construction (the existing
tests, and any third-party caller) has no position. Treating "unknown" as "whole
line" preserves every pre-existing classification outcome (FR-005) instead of
inventing a new fallback rule.

## D3 — the source issue is promoted, not re-scanned

Promotion happens on the already-discovered reference (`IssueReference.classification`
→ `implementation_target`), never by inventing a row for an uncited number. A Mission
whose source issue is not mentioned anywhere keeps today's outcome (US2 scenario 4).

## D4 — derivation sources are ordered, narrow, and fail-open

`meta.json` `source_description` (leading `Issue #N:` / `#N:` form), the spec's
`**Input**:` line (first reference on it), and `Closes|Fixes|Resolves #N` lines. A
free-form blurb that merely mentions a number in passing does not promote it, and an
unreadable `meta.json` degrades to the spec-derived sources (NFR-002) rather than
raising inside the approval blocker, which must fail closed only on its own rule.
