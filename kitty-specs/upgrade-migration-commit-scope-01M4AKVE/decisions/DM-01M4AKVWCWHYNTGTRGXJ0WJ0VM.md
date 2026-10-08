# Decision Moment `01M4AKVWCWHYNTGTRGXJ0WJ0VM`

- **Mission:** `upgrade-migration-commit-scope-01M4AKVE`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.hook-bypass`
- **Input key:** `hook_bypass_policy`
- **Status:** `resolved`
- **Created:** `2026-10-07T07:22:23.516488+00:00`
- **Resolved:** `2026-10-07T09:46:22.988157+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

The migration commit retries with --no-verify when a hook rejects it. Remove the bypass entirely (a rejected commit leaves the tree migrated and uncommitted with the existing skip warning), or keep a bypass under some condition?

## Options

- remove the bypass; rejected commit = migrated, uncommitted, warned (recommended)
- keep the bypass behind an explicit flag
- Other

## Final answer

remove the bypass; rejected commit = migrated, uncommitted, warned (recommended)

## Rationale

_(none)_

## Change log

- `2026-10-07T07:22:23.516488+00:00` — opened
- `2026-10-07T09:46:22.988157+00:00` — resolved (final_answer="remove the bypass; rejected commit = migrated, uncommitted, warned (recommended)")
