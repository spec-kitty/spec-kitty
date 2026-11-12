# Decision Moment `01M78KX2MEE320MDQE92PVBATB`

- **Mission:** `approval-honesty-01M78J9S`
- **Origin flow:** `plan`
- **Slot key:** `plan.identity.carry-forward`
- **Input key:** `carry_forward`
- **Status:** `resolved`
- **Created:** `2026-11-12T19:31:39.278275+00:00`
- **Resolved:** `2026-11-12T19:31:41.196133+00:00`
- **Resolved by:** `agent`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

What does approved->done carry when the recorded approval predates the fix?

## Options

_(none)_

## Final answer

Carry the recorded approval's reviewer and reference verbatim (an honest copy of history, C-002); if no readable approval exists, the asserted --agent with force-override, else refuse with the existing placeholder refusal. Never the git user.

## Rationale

Agent design call: the fabrication happened at the old approval; rewriting it would violate append-only history.

## Change log

- `2026-11-12T19:31:39.278275+00:00` - opened
- `2026-11-12T19:31:41.196133+00:00` - resolved (final_answer="Carry the recorded approval's reviewer and reference verbatim (an honest copy of history, C-002); if no readable approval exists, the asserted --agent with force-override, else refuse with the existing placeholder refusal. Never the git user.")
