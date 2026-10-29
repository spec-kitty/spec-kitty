# Decision Moment `01M5ZD4PNEEMAFHA7SN4VJZR2N`

- **Mission:** `status-contract-readers-01M5ZAAC`
- **Origin flow:** `plan`
- **Slot key:** `plan.actor.events-decoder-gate`
- **Input key:** `events_decoder_gate`
- **Status:** `resolved`
- **Created:** `2026-10-27T19:24:37.422413+00:00`
- **Resolved:** `2026-10-27T19:24:40.634754+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

spec-kitty-events 11.0.0 diary.decode_actor refuses the 5-key actor; how do we proceed?

## Options

- Split: 4-key now, source later
- Events first, then full shape
- Fill frontmatter in 4-key now

## Final answer

Split: every agent/operator write path emits the 4-key structured actor now (profile from invocation, --profile or compact --agent only); frontmatter fill and profile_source wait for an events release whose decoder accepts the fifth key, rolled out readers-first then writers via an explicit pin-floor bump

## Rationale

_(none)_

## Change log

- `2026-10-27T19:24:37.422413+00:00` — opened
- `2026-10-27T19:24:40.634754+00:00` — resolved (final_answer="Split: every agent/operator write path emits the 4-key structured actor now (profile from invocation, --profile or compact --agent only); frontmatter fill and profile_source wait for an events release whose decoder accepts the fifth key, rolled out readers-first then writers via an explicit pin-floor bump")
