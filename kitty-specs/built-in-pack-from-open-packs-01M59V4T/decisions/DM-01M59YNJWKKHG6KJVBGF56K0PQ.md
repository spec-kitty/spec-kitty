# Decision Moment `01M59YNJWKKHG6KJVBGF56K0PQ`

- **Mission:** `built-in-pack-from-open-packs-01M59V4T`
- **Origin flow:** `plan`
- **Slot key:** `plan.internal.descriptor-reconcile`
- **Input key:** `internal_descriptor_reconcile`
- **Status:** `resolved`
- **Created:** `2026-10-19T11:27:38.899613+00:00`
- **Resolved:** `2026-10-19T11:34:14.292055+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

open-packs packs/internal/pack.yaml lacks pack_level/active_charter/pack_drg (core schema requires pack_level) and adds pack_version 1.0.0. How to reconcile?

## Options

- PR to open-packs restoring core fields (keep pack_version; relax core test)
- Relax core descriptor to infer org level by convention
- Other

## Final answer

PR to open-packs restoring core fields (keep pack_version; relax core test)

## Rationale

_(none)_

## Change log

- `2026-10-19T11:27:38.899613+00:00` — opened
- `2026-10-19T11:34:14.292055+00:00` — resolved (final_answer="PR to open-packs restoring core fields (keep pack_version; relax core test)")
