# REASONS Canvas — untrusted-audit-relocation-pairing-01M66F6X

## Requirements

**Problem statement.** `tests/architectural/untrusted_path_audit/inventory.md`
keys each sink row by `(file, qualname, token)`. A change that only *moves* a
sink (function relocated, module renamed, joined segment unchanged) reports two
failures — a ghost row (overcount) and a missing live sink (undercount) — and a
human re-types the locator columns by hand on every relocation PR (#6642,
deferred from #5015 / PR #6622).

**Acceptance criteria.**

- A unique pure-move pairing — exactly one ghost inventory row and exactly one
  missing live sink sharing `(token, untrusted source)` — is reported as a
  single "sink moved" finding naming both locators, not a ghost + undercount
  pair.
- `audit --fix` rewrites only the paired rows' `file:line` and `qualname`
  cells; disposition and rationale are never machine-touched (#3011
  precedent); after one `--fix` run the plain audit exits 0.
- A genuinely removed sink, a genuinely new sink, a changed token, and an
  ambiguous (non-unique) pairing still fail red exactly as today.
- No inventory rationale cell keeps a hand-kept "line shifted N→M" chain.

**Definition of done.** Red-first tests prove both directions (relocation
survives; teeth keep biting) through the audit's real seams; the existing
`tests/architectural/test_untrusted_path_containment.py` passes unchanged;
changelog entry + docs (RULESET.md, inventory.md header, audit docstring)
updated; PR green and flipped to ready for review.

## Entities

- **Sink row**: one row of the inventory's markdown sink table; identity is
  the composite RowKey `(rel_path, qualname, token)`; human columns are
  disposition + rationale, machine columns are the locator (`file:line`) and
  `qualname`.
- **Ghost key**: an inventory RowKey with no live discovered sink (overcount
  set).
- **Missing key**: a discovered RowKey with no inventory row (undercount set).
- **Relocation pair**: a ghost key and a missing key sharing
  `(token, untrusted source)`, unique within that group — the audit's
  recognition of a pure move.
- **`--fix` rewrite**: the in-memory replacement of a paired row's locator
  columns, written only after a full in-memory re-audit of the would-be file
  is green (fail-closed).
- **Untrusted source**: the taint name recorded per row (`mission_slug`,
  `wp_slug`, …); invariant under a pure move, so it is part of the pair key.
