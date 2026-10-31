# Decision Moment `01M66F726F1FTHGEFREVBBXP2A`

- **Mission:** `untrusted-audit-relocation-pairing`
- **Origin flow:** `specify`
- **Step id:** `specify.success_criteria`
- **Input key:** `success_criteria`
- **Status:** `resolved`
- **Created:** `2026-10-30T13:15:32.943480+00:00`
- **Resolved:** `2026-10-30T13:18:44.834629+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How will we know this Mission is successful?

## Options

_(none)_

## Final answer

A unique pure-move pairing (one ghost + one missing sink sharing (token, untrusted source)) reports a single 'moved' finding; audit --fix re-pins only file:line and qualname and the audit goes green; genuine removals, new sinks, token changes and ambiguous pairings still fail red; rationale cells carry no line-shift chains; the existing containment test module passes unchanged.

## Rationale

_(none)_

## Change log

- `2026-10-30T13:15:32.943480+00:00` — opened
- `2026-10-30T13:18:44.834629+00:00` — resolved (final_answer="A unique pure-move pairing (one ghost + one missing sink sharing (token, untrusted source)) reports a single 'moved' finding; audit --fix re-pins only file:line and qualname and the audit goes green; genuine removals, new sinks, token changes and ambiguous pairings still fail red; rationale cells carry no line-shift chains; the existing containment test module passes unchanged.")
