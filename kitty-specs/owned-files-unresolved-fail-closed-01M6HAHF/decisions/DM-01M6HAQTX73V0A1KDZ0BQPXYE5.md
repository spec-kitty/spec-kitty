# Decision Moment `01M6HAQTX73V0A1KDZ0BQPXYE5`

- **Mission:** `owned-files-unresolved-fail-closed-01M6HAHF`
- **Origin flow:** `plan`
- **Slot key:** `plan.architecture.unresolved-signal`
- **Input key:** `unresolved_signal`
- **Status:** `resolved`
- **Created:** `2026-11-03T18:28:58.407506+00:00`
- **Resolved:** `2026-11-03T18:28:59.682919+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How does the evidence predicate tell unresolved ownership from an authored empty list, without new I/O?

## Options

_(none)_

## Final answer

By key presence: _owned_patterns_by_wp records a WP only when its task file was read, so a WP absent from scan.owned is unresolved and a present key (even an empty tuple) is authored. The scan also carries the tasks/ directory it read, so the refusal can name it. _judge checks unresolved first.

## Rationale

_(none)_

## Change log

- `2026-11-03T18:28:58.407506+00:00` - opened
- `2026-11-03T18:28:59.682919+00:00` - resolved (final_answer="By key presence: _owned_patterns_by_wp records a WP only when its task file was read, so a WP absent from scan.owned is unresolved and a present key (even an empty tuple) is authored. The scan also carries the tasks/ directory it read, so the refusal can name it. _judge checks unresolved first.")
