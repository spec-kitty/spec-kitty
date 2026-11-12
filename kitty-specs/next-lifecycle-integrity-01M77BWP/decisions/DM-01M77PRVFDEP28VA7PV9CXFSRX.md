# Decision Moment `01M77PRVFDEP28VA7PV9CXFSRX`

- **Mission:** `next-lifecycle-integrity-01M77BWP`
- **Origin flow:** `plan`
- **Slot key:** `plan.next.authoritative_run_scope`
- **Input key:** `authoritative_run_scope`
- **Status:** `resolved`
- **Created:** `2026-11-12T11:02:32.173573+00:00`
- **Resolved:** `2026-11-12T11:02:36.043541+00:00`
- **Resolved by:** `operator`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

Scope of 'authoritative run' for the never-rewind gate vs the widened front phase

## Options

- A: split by use
- C: tasks authoritative
- B: as briefed

## Final answer

A: split by use

## Rationale

Operator ruling 2026-11-12 (WP02 escalation): one helper with a parameter. Blocked/terminal gate treats runs at discovery/research/specify/plan/tasks as stale; front-phase board dispatch overrides only absent/untouched/discovery/research/specify/plan runs, so a run at tasks advances to analyze via the engine (forward step). Keeps test_advance_of_an_already_walked_run_keeps_dag_progression green and MissionRunCompleted reachable.

## Change log

- `2026-11-12T11:02:32.173573+00:00` - opened
- `2026-11-12T11:02:36.043541+00:00` - resolved (final_answer="A: split by use")
