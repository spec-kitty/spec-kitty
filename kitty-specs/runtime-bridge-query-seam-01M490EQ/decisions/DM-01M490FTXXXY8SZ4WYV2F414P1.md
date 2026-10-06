# Decision Moment `01M490FTXXXY8SZ4WYV2F414P1`

- **Mission:** `runtime-bridge-query-seam-01M490EQ`
- **Origin flow:** `specify`
- **Slot key:** `specify.compat.public_surface`
- **Input key:** `public_surface`
- **Status:** `resolved`
- **Created:** `2026-10-06T16:24:31.421854+00:00`
- **Resolved:** `2026-10-06T16:24:35.651179+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How do the public query/answer names stay reachable from runtime_bridge after the move?

## Options

- plain re-exports (same objects), no delegates
- forwarding delegates
- Other

## Final answer

plain re-exports (same objects), no delegates: query_current_state, answer_decision_via_runtime, QueryModeValidationError, MissionNotFoundError, DecisionGitLogUnavailable stay importable from runtime.next.runtime_bridge; mission 1 (#2561) retired forwarding delegates and they must not return

## Rationale

_(none)_

## Change log

- `2026-10-06T16:24:31.421854+00:00` — opened
- `2026-10-06T16:24:35.651179+00:00` — resolved (final_answer="plain re-exports (same objects), no delegates: query_current_state, answer_decision_via_runtime, QueryModeValidationError, MissionNotFoundError, DecisionGitLogUnavailable stay importable from runtime.next.runtime_bridge; mission 1 (#2561) retired forwarding delegates and they must not return")
