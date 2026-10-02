# Decision Moment `01M3V4BZBQBA8RGHDJ7T3XSKCH`

- **Mission:** `coord-artifact-single-home-01M3V4BE`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.forked-log-recovery`
- **Input key:** `forked_log_recovery`
- **Status:** `resolved`
- **Created:** `2026-10-01T07:02:57.143492+00:00`
- **Resolved:** `2026-10-01T07:06:43.550193+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

For coordination missions whose status/decision log is ALREADY forked across primary and coordination: is detection plus operator guidance enough (doctor reports the fork, repair never drops data), or must the mission also merge the forked logs automatically?

## Options

- Detect + guide, no auto-merge
- Auto-merge forked logs
- Other

## Final answer

Detect + guide, no auto-merge: doctor reports an already-forked log precisely, --repair never drops data, and the output tells the operator how to reconcile; automatic Lamport re-sequencing is out of scope (#4941).

## Rationale

_(none)_

## Change log

- `2026-10-01T07:02:57.143492+00:00` — opened
- `2026-10-01T07:06:43.550193+00:00` — resolved (final_answer="Detect + guide, no auto-merge: doctor reports an already-forked log precisely, --repair never drops data, and the output tells the operator how to reconcile; automatic Lamport re-sequencing is out of scope (#4941).")
