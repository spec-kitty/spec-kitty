# Decision Moment `01M6VYSM25F05QDD8FTS508KHZ`

- **Mission:** `nightly-reds-remediation-01M6VYS1`
- **Origin flow:** `specify`
- **Slot key:** `specify.rules.invariants`
- **Input key:** `invariants`
- **Status:** `resolved`
- **Created:** `2026-11-07T21:31:52.773524+00:00`
- **Resolved:** `2026-11-07T21:31:54.024929+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

What must always hold, and which test changes are forbidden?

## Options

_(none)_

## Final answer

A test is never weakened to green (no subset or negation assertions, no deleting a pin without a stronger home); the git-remedies gate allowlist stays empty; checkout_file_recipe, not restore_recipe, renders the file-restore remedy because restore_recipe would drop the staged edit kept by the staged_differs branch (5b822c28ca) and fails for index_only; the #6754 seed-actor guard stays; charter interview keeps its own _emit_error JSON shape, distinct from charter status typed envelope.

## Rationale

_(none)_

## Change log

- `2026-11-07T21:31:52.773524+00:00` - opened
- `2026-11-07T21:31:54.024929+00:00` - resolved (final_answer="A test is never weakened to green (no subset or negation assertions, no deleting a pin without a stronger home); the git-remedies gate allowlist stays empty; checkout_file_recipe, not restore_recipe, renders the file-restore remedy because restore_recipe would drop the staged edit kept by the staged_differs branch (5b822c28ca) and fails for index_only; the #6754 seed-actor guard stays; charter interview keeps its own _emit_error JSON shape, distinct from charter status typed envelope.")
