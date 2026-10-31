# Mission Specification: untrusted audit relocation pairing

**Mission Branch**: `issue-6642-untrusted-audit-relocation-pairing`
**Created**: 2026-10-30
**Status**: Draft
**Input**: Issue spec-kitty/spec-kitty#6642 — "Make untrusted_path_audit/inventory.md survive a pure sink relocation without a hand re-pin". Operator guidance: run the full governed mission; keep the ratchet's teeth; prove both directions with tests.

## Problem

`tests/architectural/untrusted_path_audit/inventory.md` keys each sink row by the
composite `(file, qualname, token)`. A change that only **moves** a sink — the
function is relocated into another module or function, or the module is renamed,
and the joined segment (the token) is unchanged — is reported as **two** failures:
the old row is a ghost (overcount) and the live sink is undocumented
(undercount). The human part of the row (disposition + rationale) is unchanged
by a move, yet every relocation PR re-types the locator columns (`file:line`,
`qualname`) by hand. Several rationale cells have accreted hand-kept
"line shifted N→M by mission …" relocation logs that duplicate git history.

Reproduced on main@512567ee: relocating one discovered sink to a renamed module
(with token/source unchanged) yields exactly one `check_undercount` error and one
`check_overcount` error.

## Chosen mechanism (issue proposal 1 + 3)

Pair a pure move automatically; do **not** restructure the inventory file format
(proposal 2 — a separate key-stable human file + generated locator table — is
recorded as a rejected alternative: it rewrites the audit's contract with every
downstream consumer for no additional acceptance value, and the single-file
hand-curated table remains the disposition source of truth).

1. **Relocation pairing.** After the undercount and overcount guards compute
   their unmatched sets, the audit pairs a ghost row with a missing live sink
   when they share `(token, untrusted source)` **and that pairing is unique**
   (exactly one ghost and exactly one missing sink in that `(token, source)`
   group). A paired move is reported as a **single** "sink moved" finding that
   names the old and new locators, instead of a ghost failure plus an
   undercount failure. Two fail-safe guards on the pair key:
   - **Source comparand (canonical machine string).** The untrusted source is
     compared by *exact equality* between the discovered row's machine string
     (`mission_slug`, `st.mission_slug`, `.get('mission_slug')`,
     `slug=mission_slug`, …) and the inventory row's `untrusted source` cell.
     An empty or hand-annotated prose source cell (e.g. `mission_slug
     (operator --mission selector)`) does not pair — the row stays red
     exactly as today, and the audit prints a distinct diagnostic note naming
     the non-pairing reason. To make the equality meaningful, this mission
     also adds a **source-cell canonicality check**: every live
     (non-`[inventory-only]`) inventory row whose key is discovered must carry
     a source cell exactly equal to the discovered `untrusted_source`, and
     the six hand-tuned cells on main are re-pinned to the machine string
     (hand annotations move to the rationale).
   - **Truncated tokens never auto-pair.** A token stored with the `…`
     truncation marker is excluded from automatic pairing: a genuine removal
     of one sink plus a genuine new sink sharing a 60-char prefix would
     otherwise be indistinguishable from a move (the row identity itself uses
     the truncated token, so no in-memory re-audit can catch it). Truncated
     rows stay red and are re-pinned by hand.
2. **`--fix` mode.** `python -m tests.architectural.untrusted_path_audit.audit
   --fix` rewrites **only** the paired rows' machine locator columns
   (`file:line` and `qualname`) in `inventory.md`. Disposition and rationale
   cells are never rewritten (#3011 `rekey_inventory.py` precedent: never
   overwrite hand-adjudicated columns). `--fix` is fail-closed: it re-runs every
   audit check against the would-be rewritten inventory **in memory** and writes
   the file only if the result is fully green; any other error aborts the write.
3. **Ratchet teeth unchanged for everything else.** A genuinely removed sink
   (ghost with no unique pairing), a genuinely new sink (missing with no unique
   pairing), a changed token (pairing impossible: token is the pair key), or an
   ambiguous pairing (multiple ghosts or multiple missing sinks sharing the
   `(token, source)` group) still fails red exactly as today.
4. **Stop logging history in the rationale column.** The mechanical
   "line shifted N→M by mission …" chains are dropped from the inventory
   rationale cells in this mission (git history already records them); the
   substantive provenance and disposition justifications stay. The removal is
   pattern-defined and machine-checked: after this mission no sink-table
   rationale cell may contain a line-number shift chain (arrow form
   `\d+\s*→\s*\d+` or signed-shift prose `shifted −11 by …`), asserted by the
   audit itself. The hand-kept "Disposition summary" counts at the foot of
   the inventory are reconciled to the live values and stripped of stale
   per-row locator citations (the audit's `AUDIT OK` line is the live count
   source).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A pure relocation survives with one fix run (Priority: P1)

A contributor moves a function containing an inventoried sink to another
module (or renames the module) with no other change. The audit reports ONE
actionable "sink moved from X to Y" finding instead of a ghost + undercount
pair. Running the audit with `--fix` re-pins the locator columns and the audit
goes green; no rationale or disposition text is touched.

**Why this priority**: This is the acceptance core of the issue — the manual
re-pin chore the issue exists to remove.

**Independent Test**: Drive the audit's real seams (`check_undercount`,
`check_overcount`, the new pairing seam, and `main`/`--fix`) with a simulated
relocation; assert the single moved finding, the `--fix` rewrite of only the
locator columns, and green after the fix.

**Acceptance Scenarios**:

1. **Given** the current green tree, **When** one inventory-documented sink is
   relocated (rel_path and/or qualname changed, token and untrusted source
   unchanged, non-truncated token, canonical source cell, and the move leaves
   every path-level tripwire satisfied), **Then** the audit exits non-zero
   with exactly one relocation finding naming both locators (not one ghost +
   one undercount error).
2. **Given** that state, **When** the audit runs with `--fix`, **Then**
   `inventory.md`'s row gets its `file:line` and `qualname` cells rewritten to
   the live sink's values, every other cell (token, source, sink op,
   disposition, rationale) is byte-identical, and a subsequent plain audit run
   exits 0.
3. **Given** `--fix` is run while any non-relocation error exists (bad
   disposition, unparseable row, another unrelated ghost), **Then** the file is
   not written and the errors are reported (fail-closed).

### User Story 2 - The ratchet keeps its teeth (Priority: P1)

A sink is genuinely removed, or a genuinely new sink appears, or a sink's
content changes (new token), or a pairing is ambiguous. The audit fails red
exactly as today — no auto-pairing, no silent pass.

**Why this priority**: The issue demands the guards keep their current
strictness for every other case; a relocation-tolerant audit that re-blinds the
tripwires is a security regression.

**Independent Test**: Drive the same seams with each degenerate state and
assert red with the existing error shapes.

**Acceptance Scenarios**:

1. **Given** a green tree, **When** a documented sink is deleted with no
   replacement, **Then** the overcount/ghost error fires (exit non-zero).
2. **Given** a green tree, **When** a brand-new sink appears with no matching
   ghost, **Then** the undercount error fires (exit non-zero).
3. **Given** a relocated sink whose token also changed, **Then** no pairing
   occurs and both the ghost and undercount errors fire (token is the pair key).
4. **Given** two ghosts and one missing sink sharing the same
   `(token, source)`, **Then** the pairing is ambiguous and both directions
   fail red.
5. **Given** two missing sinks and one ghost sharing the same
   `(token, source)`, **Then** the pairing is ambiguous and both directions
   fail red.

### User Story 3 - Rationale cells stop being relocation logs (Priority: P2)

A reviewer reading `inventory.md` sees disposition justifications and
provenance, not "line shifted 1902→1933 by mission …" chains. Future
relocations leave no new chains (the locator is machine-maintained via
`--fix`).

**Why this priority**: The issue names the accreted history chains as friction;
it is cleanup that rides along with the mechanism, not the acceptance core.

**Independent Test**: The audit stays green after the trim (the rows' identity
columns are untouched); the diff shows only rationale prose changes.

**Acceptance Scenarios**:

1. **Given** the trimmed inventory, **When** the audit runs, **Then** it exits 0
   (row identity columns unchanged by the trim).
2. **Given** the PR diff, **Then** no inventory row's token, source, sink op or
   disposition cell changed — only rationale prose and (where paired) locator
   columns.

### Edge Cases

- Two discovered sinks collapse to one composite key (existing
  `build_discovered_key_map` behaviour): pairing counts keys, not rows; no
  change.
- Truncated tokens (60-char `…` prefix): **never auto-paired** — a genuine
  removal plus a genuine new sink sharing the prefix is indistinguishable
  from a move by any in-memory check, so those rows stay red for a hand
  re-pin.
- An `[inventory-only]` ghost: already exempt from the overcount guard, so it
  never enters the ghost set and can never be paired.
- **Path-level tripwires are relocation-blind by design (scope boundary).**
  `KNOWN_CANDIDATE_FILES` (check 3) and the FR-009 `mission_metadata.py`
  presence check (check 4) key on locator paths. Relocating the *last* sink
  out of a known-candidate module, or renaming `mission_metadata.py`, still
  requires the hand tripwire edit and stays red; `--fix`'s in-memory re-audit
  catches it and refuses to write (fail-closed). User Story 1 is scoped to
  moves that leave these path-level tripwires satisfied.
- `--fix` with no relocations at all: a plain audit run (report only, exit
  status from the checks); it must not rewrite the file when there is nothing
  to fix. `--fix` run twice: the second run finds no relocations and writes
  nothing (idempotent).
- Multiple distinct relocations in one run: each unique pairing is reported
  and fixed independently.
- Two ghosts sharing `(token, source)` with zero missing sinks: no pairing,
  both ghost errors fire (the uniqueness condition requires exactly one
  ghost AND exactly one missing).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Relocation pairing finding | As a contributor, I want a pure sink move (unique `(token, untrusted source)` match between one ghost row and one missing live sink) reported as a single "moved" finding naming both locators, so that a relocation is actionable without reading two misleading failures. | High | Open | [build] | no |
| FR-002 | `--fix` re-pins locator columns only | As a contributor, I want `audit --fix` to rewrite only the paired rows' `file:line` and `qualname` cells, so that dispositions and rationales are never machine-touched. | High | Open | [build] | no |
| FR-003 | `--fix` is fail-closed | As a security reviewer, I want `--fix` to verify the would-be rewritten inventory passes every audit check in memory before writing, so the tool can never write a non-green inventory or mask another error. | High | Open | [build] | no |
| FR-004 | Removal still fails | As a security reviewer, I want a documented sink with no live sink and no unique pairing to keep failing the overcount guard, so a genuinely removed sink is never silently accepted. | High | Open | [ratchet] | no |
| FR-005 | New sink still fails | As a security reviewer, I want a live sink with no inventory row and no unique pairing to keep failing the undercount guard, so a genuinely new sink is never silently accepted. | High | Open | [ratchet] | no |
| FR-006 | Ambiguous or token-changed pairing fails red | As a security reviewer, I want a pairing with multiple candidate ghosts or missing sinks, or a sink whose token changed, to fail both guards as today, so the audit never guesses. | High | Open | [ratchet] | no |
| FR-007 | Drop hand-kept line-shift chains | As a reviewer of the inventory, I want the mechanical "line shifted N→M" history chains removed from rationale cells, so the rationale carries judgement, not relocation logs git already records. | Medium | Open | [folded] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Zero behaviour change on a green tree | On an unmodified tree, `audit` (no flags) output and exit code are byte-identical to before this mission. | Compatibility | High | Open |
| NFR-002 | Pairing adds no scan cost | The pairing pass is O(n) over the unmatched key sets; the audit's total runtime stays within 2× the pre-mission runtime on this tree. | Performance | Medium | Open |
| NFR-003 | Pure, testable seams | The pairing and fix logic are pure functions/seams that `main` itself calls (no parallel reimplementation in tests), preserving the existing acceptance-theater pattern. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Never touch human columns | `--fix` must never rewrite the token, untrusted source, sink op, disposition or rationale cells (#3011 precedent). | Technical | High | Open |
| C-002 | Single-file inventory format | The inventory stays one hand-curated markdown file keyed by the composite row identity; no format restructuring (proposal 2 rejected). | Technical | High | Open |
| C-003 | Existing seam signatures stay importable | `check_undercount` / `check_overcount` keep their current signatures and failure messages for the non-relocation cases; `test_untrusted_path_containment.py` must keep passing unchanged in its current assertions. | Technical | High | Open |
| C-004 | Red-first | The defect is proven with a failing test through the pre-existing entry point before the fix lands. | Process | High | Open |

### Key Entities

- **RowKey** `(rel_path, qualname, token)`: the existing composite row identity.
- **Ghost key**: an inventory RowKey with no live discovered sink.
- **Missing key**: a discovered RowKey with no inventory row.
- **Relocation pair**: a ghost key and a missing key sharing `(token, untrusted source)`, unique within that group.
- **`--fix` rewrite**: in-memory replacement of a paired row's `file:line` and `qualname` cells, written only after a full in-memory re-audit passes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A simulated pure relocation (module rename or function move, token unchanged) produces exactly one audit finding that names both the old and new locator, and zero ghost/undercount errors for that sink. — [build] · no-op passable: no
- **SC-002**: After one `--fix` run on a pure relocation, a plain audit exits 0, and the paired row's disposition and rationale cells are byte-identical to before. — [build] · no-op passable: no
- **SC-003**: A genuine removal, a genuine new sink, a token change, and an ambiguous (2-vs-1) pairing each still fail the audit non-zero with the pre-existing error classes. — [ratchet] · no-op passable: no
- **SC-004**: No inventory rationale cell contains a "line shifted N→M" chain after this mission (asserted by a test against the regex `\d+\s*→\s*\d+` on every sink-table rationale cell), and the audit is green on the trimmed inventory. — [folded] · no-op passable: no
- **SC-005**: The full existing architectural test module `tests/architectural/test_untrusted_path_containment.py` passes unchanged on the fixed tree. — [ratchet] · no-op passable: no

## References

- Issue: spec-kitty/spec-kitty#6642 (deferred from #5015, PR #6622).
- Precedent to avoid: #3011 (`rekey_inventory.py` overwriting hand-adjudicated rows).
- Companion-gate friction named by #5015 from the #5008/#4928 landing.
- Rejected alternative: issue proposal 2 (split machine/human columns, generated locator table).
