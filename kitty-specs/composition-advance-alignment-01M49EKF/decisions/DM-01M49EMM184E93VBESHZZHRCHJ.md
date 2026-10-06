# Decision Moment `01M49EMM184E93VBESHZZHRCHJ`

- **Mission:** `composition-advance-alignment-01M49EKF`
- **Origin flow:** `specify`
- **Slot key:** `specify.invariants.preserved`
- **Input key:** `invariants`
- **Status:** `resolved`
- **Created:** `2026-10-06T20:31:48.264778+00:00`
- **Resolved:** `2026-10-06T20:31:50.804111+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Which invariants must the aligned composition path preserve?

## Options

- FR-001 single dispatch, FR-008 plan-first, retrospective gate, emitter seeding, stale-plan guarantee
- Other

## Final answer

FR-001 single dispatch (never re-enter the legacy DAG dispatch), FR-008 plan-first/commit-second refusal of a WP-iteration plan without wp_resolution, the terminal retrospective gate (blocking capture -> MissionRunCompleted -> non-blocking capture), emitter seeding, and the StaleAdvancePlan guarantee when routing through commit_advance

## Rationale

_(none)_

## Change log

- `2026-10-06T20:31:48.264778+00:00` — opened
- `2026-10-06T20:31:50.804111+00:00` — resolved (final_answer="FR-001 single dispatch (never re-enter the legacy DAG dispatch), FR-008 plan-first/commit-second refusal of a WP-iteration plan without wp_resolution, the terminal retrospective gate (blocking capture -> MissionRunCompleted -> non-blocking capture), emitter seeding, and the StaleAdvancePlan guarantee when routing through commit_advance")
