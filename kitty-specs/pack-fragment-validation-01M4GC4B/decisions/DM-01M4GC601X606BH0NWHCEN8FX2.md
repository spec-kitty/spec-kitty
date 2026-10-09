# Decision Moment `01M4GC601X606BH0NWHCEN8FX2`

- **Mission:** `pack-fragment-validation-01M4GC4B`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.sibling-pack-endpoints`
- **Input key:** `sibling_pack_endpoint_policy`
- **Status:** `resolved`
- **Created:** `2026-10-09T13:03:32.925631+00:00`
- **Resolved:** `2026-10-09T13:03:34.964360+00:00`
- **Resolved by:** `operator-delegated-scope`
- **Opened by:** `orchestrator`
- **Other answer:** `false`

## Question

A qualified drg/fragment.yaml endpoint names a node that neither the built-in catalog nor this pack declares (e.g. a sibling org pack's node). How does standalone pack validation report it?

## Options

- error (fail closed, same as the sharded layout)
- advisory
- skip

## Final answer

error (fail closed, same as the sharded layout)

## Rationale

Operator-delegated scope for #5833: same fail-closed behaviour as the sharded drg/*.graph.yaml path; docs/changelog state that standalone validation cannot see undeclared sibling-pack targets. Matches the issue's Expected section.

## Change log

- `2026-10-09T13:03:32.925631+00:00` — opened
- `2026-10-09T13:03:34.964360+00:00` — resolved (final_answer="error (fail closed, same as the sharded layout)")
