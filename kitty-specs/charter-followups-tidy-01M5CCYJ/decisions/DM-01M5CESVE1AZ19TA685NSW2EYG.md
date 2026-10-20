# Decision Moment `01M5CESVE1AZ19TA685NSW2EYG`

- **Mission:** `charter-followups-tidy-01M5CCYJ`
- **Origin flow:** `specify`
- **Slot key:** `specify.migrations.repo-requirement`
- **Input key:** `migration_repo_requirement`
- **Status:** `resolved`
- **Created:** `2026-10-20T10:48:04.801820+00:00`
- **Resolved:** `2026-10-20T10:48:08.206736+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

#6539: how should the upgrade runner handle a migration that needs a git repository when run outside one?

## Options

- Declared flag
- apply()-raise = failed
- Pin with a gate only
- Other

## Final answer

Declared flag: BaseMigration.requires_git_repository ClassVar; runner checks it before detect() and skips unrecorded; apply()-level NotInsideRepositoryError catch removed so a raise inside apply() is a recorded failed (retries).

## Rationale

_(none)_

## Change log

- `2026-10-20T10:48:04.801820+00:00` — opened
- `2026-10-20T10:48:08.206736+00:00` — resolved (final_answer="Declared flag: BaseMigration.requires_git_repository ClassVar; runner checks it before detect() and skips unrecorded; apply()-level NotInsideRepositoryError catch removed so a raise inside apply() is a recorded failed (retries).")
