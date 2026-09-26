# Post-spec squad — reviewer-renata (anti-laziness / scope / testability)

Verdict: FOLD-THEN-PROCEED. Dispositions:

| # | Sev | Finding | Disposition |
|---|-----|---------|-------------|
| 1 | MAJOR | Filled example row with a real `FR-0NN` id would add a phantom declared FR and make the scaffold substantive | accepted — C-007 (`FR-EXAMPLE` id), FR-004 asserts declared-id set unchanged |
| 2 | MAJOR | FR-004 "no-op passable: no" dishonest (`take_columns=2` ignores trailing columns) | accepted — relabelled `[ratchet]` · yes, control = same scaffold with Title/User Story filled is substantive |
| 3 | MAJOR | FR-003 control inverted / not same fixture; helper-only proof of "no coverage change" | accepted — one fixture (labelled + mis-placed rows); coverage asserted through the map-requirements seam vs unlabelled twin |
| 4 | MAJOR | FR-010 "match" conflicts with keeping drift out of scope; review `actions/index.yaml` override unaddressed | changed — operator widened scope: full resync of every drifted override with a built-in counterpart (DM-01M3EX8WE96MHDTQTEE5M8WT85) |
| 5 | MAJOR | US3 AS2 untestable via compact charter context | accepted — surface = direct scope edge in regenerated graph + `resolve_context` at depth 1 |
| 6 | MINOR | C-006 vs template legend gloss | accepted — gloss allowed, explicitly marked as summary |
| 7 | MINOR | FR-007 passable by string grep | accepted — test also resolves the named id via `charter context --include tactic:` |
| 8 | MINOR | NFR-001 mechanism unnamed / no-op passable | accepted — names corpus ratchet + before/after declared-id diff |
| 9 | MINOR | Mission-type scope implicit | accepted — Out of Scope lists documentation/research/plan templates |
