# Decision Moment `01M491JXCBGP89BVMJAMKZR41T`

- **Mission:** `charter-pack-cutover-01M491G6`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.tier-vocabulary`
- **Input key:** `tier_vocabulary_scope`
- **Status:** `resolved`
- **Created:** `2026-10-06T16:43:40.811256+00:00`
- **Resolved:** `2026-10-06T17:41:20.191902+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Should this mission also fold in #5825 (the built-in tier spelled 'built-in' vs 'builtin', and pack-path literals with no single home), or only its path half (.kittify/doctrine / charter-packs constants), leaving tier spelling to #5825?

## Options

- Fold all of #5825
- Path half only
- Neither: leave #5825 separate
- Other

## Final answer

Path half only (B): the mission centralises the .kittify/doctrine / .kittify/charter-packs path constants it already moves; the built-in vs builtin tier spelling stays in #5825 (41 src sites in 22 files, 132 test sites, and a consumer-visible JSON value such as charter context --json "source": "builtin", so A is not trivial).

## Rationale

_(none)_

## Change log

- `2026-10-06T16:43:40.811256+00:00` — opened
- `2026-10-06T17:41:20.191902+00:00` — resolved (final_answer="Path half only (B): the mission centralises the .kittify/doctrine / .kittify/charter-packs path constants it already moves; the built-in vs builtin tier spelling stays in #5825 (41 src sites in 22 files, 132 test sites, and a consumer-visible JSON value such as charter context --json "source": "builtin", so A is not trivial).")
