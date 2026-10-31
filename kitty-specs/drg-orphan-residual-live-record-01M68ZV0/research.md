# Research — drg-orphan-residual-live-record-01M68ZV0 (#6513)

Discovery recorded after grounding, before the spec (the mission's `discovery` step). The facts
below were reproduced in this clone; nothing here is quoted from prose alone.

## Decision 1 — The four new orphans must not be wired, and the ceiling must not move

`test_shipped_graph_orphan_count_within_documented_residual` failed at `f1663393` because that tree
carried ceiling **21** while the shipped graph measured **25**. The four extra nodes are
`mission_step_contract:plan/{plan,research,review,specify}`, vendored by the built-in pin bump of
PR #6379 and tracked by #6432; commit `bd7fdb7f36` (the #6437 fold) raised the constant 21 -> 25.

Evidence that 25 is the correct number and that no edge may be invented:

- `_EDGELESS_BY_CONSTRUCTION` in `tests/charter_offering/drg/migration/test_extractor_projection.py`
  lists all 21 step contracts, including the four `plan/*` ones: the step-contract fragment ships
  `edges: []` and the activation engine resolves a contract by URN lookup on the
  `(mission_type, action)` join, never by traversal.
- `_INTENTIONAL_ORPHANS` = `_EDGELESS_BY_CONSTRUCTION` (21) | `_AWAITING_REFERENCES` (3) |
  `_NOT_A_TRAVERSAL_TARGET` (1) | `_ACTIVATED_BUT_ORPHANED` (0) | `_DIRECT_ACTIVATION_ONLY` (1)
  = 26 pure orphans; `_SHIPPED_ORPHANS` subtracts the single overlay-resolved node
  (`asset:common-docs-structural-lint`) = 25, matching the measurement.
- Measured on this checkout: `load_built_in_graph()` -> 358 nodes, 1,069 edges, **25** nodes with
  no incident edge. Wiring one of the four would be metric-gaming (D-C2 / C-003).

## Decision 2 — What is actually still broken is the *documented* residual, so the fix is docs + a guard

The issue's own remedy has two halves: wire an edge, **or** update the residual doc and raise the
ceiling with rationale. The second half cannot be executed as written:

- The record the ceiling's failure message and docstring name,
  `kitty-specs/mission-lifecycle-dispatch-drg-closeout-01KV0S99/drg-orphan-residual.md`, sits under
  `kitty-specs/`, one of the four immutable archive roots in
  `tests/architectural/test_archive_root_byte_identical.py`. Editing it fails that gate.
- Its last recorded state is ceiling **29 -> 30 over 17 step contracts** (2026-07-23 and
  2026-07-26 entries). The shipped reality is **25 over 21**. A curator reading the canonical #1923
  record is wrong by five nodes.
- The 21 -> 25 rationale was parked in a mission-scoped file
  (`kitty-specs/charter-synthesis-graph-and-languages-01M59RZ5/research/orphan-residual-addendum.md`),
  itself under a frozen root and not referenced from the ceiling test.
- Nothing binds `DOCUMENTED_ORPHAN_RESIDUAL` to any record: the assertion is `orphans <= ceiling`,
  so a one-line raise with a comment goes green and the documented residual is never consulted.

Conclusion: the current-state record must move to a writable home, the gate's instructions must
point there, and a guard must make that record load-bearing in both directions (a growth and a
shrink). This is the whole mission; the ceiling stays 25.

## Decision 3 — The record lives in the existing DRG architecture page

`docs/architecture/charter-synthesis-drg.md` gains a self-contained "The shipped-graph orphan
residual (current state)" section. A new docs page would additionally need a page-inventory row, an
explanation-ToC entry, redirect/related validation and spelling review — a blast radius wider than
the issue. The page is already inventory-registered, so the only generated follow-on is its row in
`docs/development/docs-retrieval-index.yaml` (abstract + the four new anchors), regenerated with
`scripts.docs.docs_index --write`.

## Decision 4 — Machine-readable membership is a delimited block, not a table

The section lists the 25 URNs between `<!-- drg-orphan-residual:begin -->` and
`<!-- drg-orphan-residual:end -->`; the guard parses only whole backticked URN spans inside that
block. Prose, historical sections and tables elsewhere on the page cannot satisfy it, and an inline
span such as `edges: []` cannot parse as a member. The kind alternation is derived from `NodeKind`,
so a doctrine kind added later still parses instead of silently dropping a recorded URN.

## Evidence gathered

- `uv run --frozen python -m pytest -q tests/specify_cli/cli/commands/test_doctrine_regenerate_graph.py`
  -> 5 passed on pristine `main` `dfe9efb0e8` (the reported red no longer reproduces).
- Recompute snippet (as now printed in the record) -> 25 URNs, listed in the record.
- `git log -S"DOCUMENTED_ORPHAN_RESIDUAL = 25" -- tests/.../test_doctrine_regenerate_graph.py`
  -> `bd7fdb7f36`, whose message names #6379 / #6432 and the four plan contracts.
- `tests/architectural/test_archive_root_byte_identical.py` -> `kitty-specs/` is an immutable
  exclusion root (26 passed on the mission branch).

## Open questions (none blocking)

- Whether `glossary_pack:spec-kitty-core` ever gains its enforcement references (an `_AWAITING_REFERENCES`
  member awaiting a follow-up mission) — out of scope here, recorded in the live record.
- Whether the pre-existing red tests named by #6798, #6801, #6816 and #5927 stay red past this
  window — not caused by and not fixed by this change; cited as context only.
