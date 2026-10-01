# Decision Moment `01M3SSYCZP47HX0VDVNFCXRV7Z`

- **Mission:** `git-paths-are-data-01M3SSXR`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.migration-boundary`
- **Input key:** `migration_boundary`
- **Status:** `resolved`
- **Created:** `2026-09-30T18:41:32.150782+00:00`
- **Resolved:** `2026-09-30T18:41:50.657239+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Which git call sites does this mission migrate onto the shared git module?

## Options

- Every path-listing call site (status --porcelain, ls-files, ls-tree, --name-only, --name-status); plain git runners go to a follow-up issue
- Every git argv in src
- Only ref_advance
- Other

## Final answer

Every path-listing call site (status --porcelain, ls-files, ls-tree, --name-only, --name-status); plain git runners go to a follow-up issue

## Rationale

_(none)_

## Change log

- `2026-09-30T18:41:32.150782+00:00` — opened
- `2026-09-30T18:41:50.657239+00:00` — resolved (final_answer="Every path-listing call site (status --porcelain, ls-files, ls-tree, --name-only, --name-status); plain git runners go to a follow-up issue")
