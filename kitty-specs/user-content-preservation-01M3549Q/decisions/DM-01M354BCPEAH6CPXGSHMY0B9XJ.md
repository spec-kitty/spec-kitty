# Decision Moment `01M354BCPEAH6CPXGSHMY0B9XJ`

- **Mission:** `user-content-preservation-01M3549Q`
- **Origin flow:** `specify`
- **Slot key:** `specify.contract.overwrite-behavior`
- **Input key:** `overwrite_behavior`
- **Status:** `resolved`
- **Created:** `2026-09-22T17:59:20.526089+00:00`
- **Resolved:** `2026-09-22T18:01:40.549612+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

When a mutating flow is about to overwrite a pre-existing user-authored file it did not create, what is the contract?

## Options

- refuse+force
- backup+warn
- hybrid-per-flow

## Final answer

Hybrid per-flow: refuse + require --force where the user drives the command directly and a flag is natural (intake brief); back up the existing foreign file to a timestamped sidecar + warn + proceed where refusing would break an in-progress workflow (git-hook install during implement — detect a foreign hook by signature, back it up, and surface it in output). Removals remain preserve-in-place + warn via the existing guard.

## Rationale

_(none)_

## Change log

- `2026-09-22T17:59:20.526089+00:00` — opened
- `2026-09-22T18:01:40.549612+00:00` — resolved (final_answer="Hybrid per-flow: refuse + require --force where the user drives the command directly and a flag is natural (intake brief); back up the existing foreign file to a timestamped sidecar + warn + proceed where refusing would break an in-progress workflow (git-hook install during implement — detect a foreign hook by signature, back it up, and surface it in output). Removals remain preserve-in-place + warn via the existing guard.")
