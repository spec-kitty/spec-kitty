# Research: Reach-only membership fails closed (#6454)

Phase 0 for this Mission builds on the discovery research recorded in
`kitty-specs/reach-only-fail-closed-research-01M5WZCH/research.md` (root cause reproduced live,
caller table, decisions 1-5, red-first test list). Nothing below replaces it.

## Decisions

- **Decision**: membership order manifest → record → fail closed.
  **Rationale**: operator rulings 1 and 2; the record is a superset of manifest entries and the
  synthesis-shaped edge still gates membership.
  **Alternatives considered**: a named error when neither is readable (operator triage comment,
  2026-10-19) — rejected by the later ruling, because it would stop action context from
  rendering at all.
- **Decision**: warning via the module logger at WARNING.
  **Rationale**: the bundle already uses `_LOGGER.warning`; the CLI logging bootstrap routes
  WARNING records to the terminal. `effective_set.py` logs its fail-closed reads at DEBUG, which
  would not reach the operator, so it is not copied here.
  **Alternatives considered**: returning a warnings list — would change the public signature of
  `reach_only_ids` and both consumers (rejected, C-001).
- **Decision**: the append path keeps its lenient read (decision moment
  `01M5WZH28BW0HC6QNSRRGWX4JP`).

## Supply chain

No dependency is added, upgraded or removed; DIRECTIVE_051 controls do not apply.
