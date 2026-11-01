# Design decisions — drg-orphan-residual-live-record-01M68ZV0 (#6513)

## DD-1 — The live record lives in the existing DRG architecture page (pi, 2026-10-31)

`docs/architecture/charter-synthesis-drg.md` gains a "The shipped-graph orphan residual (current
state)" section rather than a new page. Rejected alternatives:

- **A new `docs/architecture/drg-orphan-residual.md` page.** It would need a page-inventory row, an
  explanation-ToC entry, redirect/related validation and spelling review — a blast radius wider than
  the issue, in a docs-truth-up change.
- **Editing the frozen record in place.** Forbidden: `kitty-specs/` is an immutable archive root
  (`tests/architectural/test_archive_root_byte_identical.py`). The archive stays as the as-of-date
  historical record and is cited, never edited (C-002).

## DD-2 — A delimited block, not a Markdown table, is the machine-readable membership (pi)

The guard parses only backticked spans between `<!-- drg-orphan-residual:begin -->` and
`<!-- drg-orphan-residual:end -->`, and only when the span is a whole `<kind>:<id>` URN from the
known kind set. Consequences: prose and historical sections cannot satisfy the guard; an inline code
span such as `edges: []` cannot parse as a member; the record itself stays readable as a bulleted
list. A table would have coupled the guard to column layout.

## DD-3 — The guard asserts set equality, both directions (pi)

A numeric ceiling can only ever see an *excess*. Set equality is what makes a silent **raise**
impossible: a new orphan fails until it is recorded, and a recorded URN that is wired (or retired)
also fails, so a shrink must be recorded too. Both directions were proven by temporary mutation
before the PR.

## DD-4 — Two membership lists, two frames, stated instead of merged (pi)

`_SHIPPED_ORPHANS` in the extractor-projection ledger is the **pure-extractor** frame; this record
and the ceiling are the **shipped** frame (`load_built_in_graph()`). They differ only by
`_ORPHANS_RESOLVED_BY_OVERLAY` (`asset:common-docs-structural-lint`), and the record, the docstring
and the guard's docstring all say so, so neither gets "corrected" against the other (analysis
finding F1).
