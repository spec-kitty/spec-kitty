# Decision Moment `01M70VNZ46K3BZR8WVHJ81CWR0`

- **Mission:** `docsite-shared-build-01M70V33`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.shape`
- **Input key:** `build_definition_shape`
- **Status:** `resolved`
- **Created:** `2026-11-09T19:13:39.462453+00:00`
- **Resolved:** `2026-11-09T19:13:41.795042+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Should the shared docs-site build definition be a composite action or a reusable workflow?

## Options

_(none)_

## Final answer

Reusable workflow: #6936 needs job-level services:, which a composite action cannot declare (operator, 2026-11-09).

## Rationale

_(none)_

## Change log

- `2026-11-09T19:13:39.462453+00:00` - opened
- `2026-11-09T19:13:41.795042+00:00` - resolved (final_answer="Reusable workflow: #6936 needs job-level services:, which a composite action cannot declare (operator, 2026-11-09).")
