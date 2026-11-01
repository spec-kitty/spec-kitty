# Decision Moment `01M66F8JM044NQRY7JNWB1P19Y`

- **Mission:** `events-tail-multi-log-and-json`
- **Origin flow:** `specify`
- **Step id:** `specify.problem_statement`
- **Input key:** `problem_statement`
- **Status:** `resolved`
- **Created:** `2026-10-30T13:16:22.528581+00:00`
- **Resolved:** `2026-10-30T13:21:27.909309+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

What problem does this Mission solve?

## Options

_(none)_

## Final answer

spec-kitty events tail, the ADR 2026-10-13-2 D-2 local subscriber, can follow only a Mission's status.events.jsonl, and its --json flag is accepted but unused (#6611). Operators cannot watch the decision log, run journal, glossary, Op lifecycle or canonical events, and humans get raw JSON with no readable mode.

## Rationale

_(none)_

## Change log

- `2026-10-30T13:16:22.528581+00:00` — opened
- `2026-10-30T13:21:27.909309+00:00` — resolved (final_answer="spec-kitty events tail, the ADR 2026-10-13-2 D-2 local subscriber, can follow only a Mission's status.events.jsonl, and its --json flag is accepted but unused (#6611). Operators cannot watch the decision log, run journal, glossary, Op lifecycle or canonical events, and humans get raw JSON with no readable mode.")
