# Decision Moment `01M4AKVTD3XMCEAJ9TDYBBAJVT`

- **Mission:** `upgrade-migration-commit-scope-01M4AKVE`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.dirty-tree-policy`
- **Input key:** `dirty_tree_policy`
- **Status:** `resolved`
- **Created:** `2026-10-07T07:22:21.475354+00:00`
- **Resolved:** `2026-10-07T09:46:20.908704+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

When the operator's tree is already dirty before the schema-3 upgrade, should upgrade (a) refuse up front, (b) proceed and commit only paths the upgrade changed that were clean before, leaving the operator's work untouched, or (c) proceed but commit nothing?

## Options

- (b) commit only upgrade-changed clean paths (recommended)
- (a) refuse up front
- (c) never commit
- Other

## Final answer

(b) commit only upgrade-changed clean paths (recommended)

## Rationale

_(none)_

## Change log

- `2026-10-07T07:22:21.475354+00:00` — opened
- `2026-10-07T09:46:20.908704+00:00` — resolved (final_answer="(b) commit only upgrade-changed clean paths (recommended)")
