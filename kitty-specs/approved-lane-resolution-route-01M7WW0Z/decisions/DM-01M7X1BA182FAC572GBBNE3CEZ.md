# Decision Moment `01M7X1BA182FAC572GBBNE3CEZ`

- **Mission:** `approved-lane-resolution-route-01M7WW0Z`
- **Origin flow:** `plan`
- **Slot key:** `plan.fr010.committed-attributes`
- **Input key:** `fr010_committed_attributes`
- **Status:** `resolved`
- **Created:** `2026-11-20T17:51:25.736301+00:00`
- **Resolved:** `2026-11-20T17:51:29.536410+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

FR-010: should a COMMITTED built-in merge attribute (union/set) be honoured?

## Options

_(none)_

## Final answer

(a) honour committed built-in union/set only when git check-attr --source <pre-run target tip> matches the effective lookup and no merge.<name>.driver is configured; clone-local sources, merge.default, custom drivers and git<2.40 refuse; red tests for the committed-allowed case and each override bypass incl. merge=binary + custom driver (operator, 2026-11-20)

## Rationale

_(none)_

## Change log

- `2026-11-20T17:51:25.736301+00:00` - opened
- `2026-11-20T17:51:29.536410+00:00` - resolved (final_answer="(a) honour committed built-in union/set only when git check-attr --source <pre-run target tip> matches the effective lookup and no merge.<name>.driver is configured; clone-local sources, merge.default, custom drivers and git<2.40 refuse; red tests for the committed-allowed case and each override bypass incl. merge=binary + custom driver (operator, 2026-11-20)")
