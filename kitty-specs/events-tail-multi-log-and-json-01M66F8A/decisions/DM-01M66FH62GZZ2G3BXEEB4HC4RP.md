# Decision Moment `01M66FH62GZZ2G3BXEEB4HC4RP`

- **Mission:** `events-tail-multi-log-and-json-01M66F8A`
- **Origin flow:** `specify`
- **Slot key:** `specify.log-selector.kind-set`
- **Input key:** `log_selector_kind_set`
- **Status:** `resolved`
- **Created:** `2026-10-30T13:21:04.592673+00:00`
- **Resolved:** `2026-10-30T13:21:09.280669+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Which ledger kinds should the --log selector offer?

## Options

- only the kinds the issue names (status, decisions, run, glossary, ops)
- all kinds the #6603 writes gate names, incl. indexes and provenance
- kinds named by the issue plus mission v1 and canonical (seven total)

## Final answer

Seven kinds: status (default), decisions, mission, run, glossary, ops, canonical — the kinds the issue's problem statement names plus mission v1 events and the project canonical log. Index/bookkeeping logs (ops-index, op-closures, propagation-errors, policy audit, archive registry, encoding provenance) stay deferred; proportionality ruling from the delivery run's guidance.

## Rationale

_(none)_

## Change log

- `2026-10-30T13:21:04.592673+00:00` — opened
- `2026-10-30T13:21:09.280669+00:00` — resolved (final_answer="Seven kinds: status (default), decisions, mission, run, glossary, ops, canonical — the kinds the issue's problem statement names plus mission v1 events and the project canonical log. Index/bookkeeping logs (ops-index, op-closures, propagation-errors, policy audit, archive registry, encoding provenance) stay deferred; proportionality ruling from the delivery run's guidance.")
