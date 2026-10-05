# Decision Moment `01M44FNVCK8K5V0B60MVQTBS22`

- **Mission:** `nightly-suites-green-01M44FEP`
- **Origin flow:** `specify`
- **Slot key:** `specify.track-c.per-pr-home`
- **Input key:** `track_c_home`
- **Status:** `resolved`
- **Created:** `2026-10-04T22:13:44.979703+00:00`
- **Resolved:** `2026-10-04T22:13:47.482167+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Claiming tests/specify_cli/cli/commands as a per-PR shard is blocked by the nested-claim rule. How does the recipe gate get a per-PR home?

## Options

- Move the gate
- Promote the directory

## Final answer

Move the gate: the recipe scanner test moves to tests/architectural (precedent #4479); the directory stays nightly-only and is cross-referenced on #4708/#4732/#5652.

## Rationale

_(none)_

## Change log

- `2026-10-04T22:13:44.979703+00:00` — opened
- `2026-10-04T22:13:47.482167+00:00` — resolved (final_answer="Move the gate: the recipe scanner test moves to tests/architectural (precedent #4479); the directory stays nightly-only and is cross-referenced on #4708/#4732/#5652.")
