# Decision Moment `01M66YZXPKH6YXWFZYHB7H5MKT`

- **Mission:** `migration-actor-cli-spoofing-01M66YYX`
- **Origin flow:** `specify`
- **Slot key:** `specify.boundary.seed-write-capability`
- **Input key:** `seed_write_capability`
- **Status:** `resolved`
- **Created:** `2026-10-30T17:51:16.179745+00:00`
- **Resolved:** `2026-10-30T17:51:19.416881+00:00`
- **Opened by:** `operator`
- **Other answer:** `false`

## Question

How should a caller-supplied 'migration:' identity be distinguished from a genuine reconstruction seed (#6754)?

## Options

- Refuse caller-supplied seed-shaped identities at every boundary that records them verbatim (issue Option 1)
- Escape or re-parse the value into a live actor
- Add an explicit seed field to the events contract (issue Option 2)

## Final answer

Option 1: refuse a caller-supplied identity that starts with 'migration:' at every boundary that records it verbatim (agent status emit --actor, the four orchestrator-api lifecycle verbs, the hidden implement --actor), and keep in-process migration writers as the only producers. Option 2 (an explicit event field) is deferred to spec-kitty-events#92: it needs an events release and the Java write core, both frozen by ADR 2026-10-29-1. The value is never silently rewritten, so no log records an identity the caller did not write. Sourced from the operator dispatch brief for this mission and issue #6754's own Option 1.

## Rationale

_(none)_

## Change log

- `2026-10-30T17:51:16.179745+00:00` — opened
- `2026-10-30T17:51:19.416881+00:00` — resolved (final_answer="Option 1: refuse a caller-supplied identity that starts with 'migration:' at every boundary that records it verbatim (agent status emit --actor, the four orchestrator-api lifecycle verbs, the hidden implement --actor), and keep in-process migration writers as the only producers. Option 2 (an explicit event field) is deferred to spec-kitty-events#92: it needs an events release and the Java write core, both frozen by ADR 2026-10-29-1. The value is never silently rewritten, so no log records an identity the caller did not write. Sourced from the operator dispatch brief for this mission and issue #6754's own Option 1.")
