# Decision Moment `01M2FR5WMG2R2W9CC9E0ZSYPZ6`

- **Mission:** `sonar-per-pr-coverage-reuse-01M2FR32`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.orphaned-test-dirs`
- **Input key:** `orphaned_test_dirs`
- **Status:** `resolved`
- **Created:** `2026-09-14T10:42:34.256572+00:00`
- **Resolved:** `2026-09-14T10:45:31.489637+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

tests/unit and tests/specify_cli/runtime have no CI home other than the fast-tier step this mission deletes. In scope to give them one?

## Options

- Add registry rows (in scope)
- Accept the drop, file a follow-up
- Other

## Final answer

In scope: add tests/unit and tests/specify_cli/runtime to .github/ci-module-registry.yml so the matrix covers them. Restores their coverage contribution and gives them a real blocking CI home for the first time; the registry stays the single data source for what CI runs.

## Rationale

_(none)_

## Change log

- `2026-09-14T10:42:34.256572+00:00` — opened
- `2026-09-14T10:45:31.489637+00:00` — resolved (final_answer="In scope: add tests/unit and tests/specify_cli/runtime to .github/ci-module-registry.yml so the matrix covers them. Restores their coverage contribution and gives them a real blocking CI home for the first time; the registry stays the single data source for what CI runs.")
