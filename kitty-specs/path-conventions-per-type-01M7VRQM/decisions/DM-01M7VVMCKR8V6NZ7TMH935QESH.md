# Decision Moment `01M7VVMCKR8V6NZ7TMH935QESH`

- **Mission:** `path-conventions-per-type-01M7VRQM`
- **Origin flow:** `plan`
- **Slot key:** `plan.waiver.orchestrator-meta`
- **Input key:** `orchestrator_meta_waiver`
- **Status:** `resolved`
- **Created:** `2026-11-20T06:52:17.400462+00:00`
- **Resolved:** `2026-11-20T06:52:21.717170+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Does orchestrator-api honour the meta.json path-conventions waiver?

## Options

- a: honour neither waiver on orchestrator-api
- b: honour the meta.json waiver everywhere; per-run flag CLI-only
- Other

## Final answer

b: honour the meta.json waiver everywhere, orchestrator-api included, like contracts: none; only the per-run flag is CLI-only; metadata stays strict on both paths.

## Rationale

_(none)_

## Change log

- `2026-11-20T06:52:17.400462+00:00` - opened
- `2026-11-20T06:52:21.717170+00:00` - resolved (final_answer="b: honour the meta.json waiver everywhere, orchestrator-api included, like contracts: none; only the per-run flag is CLI-only; metadata stays strict on both paths.")
