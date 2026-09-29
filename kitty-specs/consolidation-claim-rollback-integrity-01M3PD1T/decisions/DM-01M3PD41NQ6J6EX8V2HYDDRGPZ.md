# Decision Moment `01M3PD41NQ6J6EX8V2HYDDRGPZ`

- **Mission:** `consolidation-claim-rollback-integrity-01M3PD1T`
- **Origin flow:** `specify`
- **Slot key:** `specify.planning-lane.self-heal-fix`
- **Input key:** `planning_self_heal_fix`
- **Status:** `resolved`
- **Created:** `2026-09-29T10:59:42.391651+00:00`
- **Resolved:** `2026-09-29T10:59:45.537315+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How is the planning-lane dependency self-heal (#5296) fixed?

## Options

- Refuse on root/target
- Gate attributes landed content
- Other

## Final answer

Refuse (fail closed) when a planning WP dependency self-heal would merge code lanes into the repository-root checkout on the target branch; guidance: consolidate code lanes first; refusal text derived from what actually moved

## Rationale

_(none)_

## Change log

- `2026-09-29T10:59:42.391651+00:00` — opened
- `2026-09-29T10:59:45.537315+00:00` — resolved (final_answer="Refuse (fail closed) when a planning WP dependency self-heal would merge code lanes into the repository-root checkout on the target branch; guidance: consolidate code lanes first; refusal text derived from what actually moved")
