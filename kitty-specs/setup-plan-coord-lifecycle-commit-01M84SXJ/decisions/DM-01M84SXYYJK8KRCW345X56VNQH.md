# Decision Moment `01M84SXYYJK8KRCW345X56VNQH`

- **Mission:** `setup-plan-coord-lifecycle-commit-01M84SXJ`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.stranded-events`
- **Input key:** `stranded_events_handling`
- **Status:** `resolved`
- **Created:** `2026-11-23T18:15:43.826305+00:00`
- **Resolved:** `2026-11-23T19:07:04.280049+00:00`
- **Resolved by:** `operator`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Existing coordination Missions may already hold SpecifyCompleted/PlanStarted/PlanCompleted events stranded, uncommitted, in the repository root checkout's status log. What should this Mission do about them?

## Options

- doctor reports them; no migration in this Mission
- migrate them onto the coordination log
- ignore them
- Other

## Final answer

doctor reports them; no migration in this Mission

## Rationale

Operator answer 1A, relayed verbatim by the dispatcher.

## Change log

- `2026-11-23T18:15:43.826305+00:00` - opened
- `2026-11-23T19:07:04.280049+00:00` - resolved (final_answer="doctor reports them; no migration in this Mission")
