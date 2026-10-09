# Decision Moment `01M4GC641KD33FRTTV6YGG9PB2`

- **Mission:** `pack-fragment-validation-01M4GC4B`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.bare-endpoint-resolution`
- **Input key:** `bare_endpoint_policy`
- **Status:** `resolved`
- **Created:** `2026-10-09T13:03:37.011413+00:00`
- **Resolved:** `2026-10-09T13:03:39.015832+00:00`
- **Resolved by:** `operator-delegated-scope`
- **Opened by:** `orchestrator`
- **Other answer:** `false`

## Question

Which resolution rule decides whether a bare or malformed fragment.yaml endpoint resolves, and how is a bare id matching more than one built-in node reported?

## Options

- runtime endpoint resolver rules; ambiguous bare id is an error
- augmentation-intent shortcut (bare target borrows source kind)
- Other

## Final answer

runtime endpoint resolver rules; ambiguous bare id is an error

## Rationale

Operator-delegated scope: unresolved bare sources/targets and malformed endpoints fail with the runtime endpoint resolver semantics, not the #5494 augmentation shortcut; ambiguous bare built-in ids handled consistently with the runtime (refused).

## Change log

- `2026-10-09T13:03:37.011413+00:00` — opened
- `2026-10-09T13:03:39.015832+00:00` — resolved (final_answer="runtime endpoint resolver rules; ambiguous bare id is an error")
