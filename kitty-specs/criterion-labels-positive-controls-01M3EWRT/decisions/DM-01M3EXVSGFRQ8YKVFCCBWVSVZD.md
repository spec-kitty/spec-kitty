# Decision Moment `01M3EXVSGFRQ8YKVFCCBWVSVZD`

- **Mission:** `criterion-labels-positive-controls-01M3EWRT`
- **Origin flow:** `plan`
- **Slot key:** `plan.scope.expected-artifacts-override`
- **Input key:** `expected_artifacts_override`
- **Status:** `resolved`
- **Created:** `2026-09-26T13:18:22.223244+00:00`
- **Resolved:** `2026-09-26T13:18:24.698597+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

expected-artifacts.yaml override is DEPRECATED/INERT and test-pinned (Decision 4 of expected-artifacts-manifest-repair). Resync, exclude, or delete?

## Options

- Exclude it
- Resync + reverse Decision 4
- Delete the override
- Other

## Final answer

Delete the override and the TestOverrideMirrorDeprecation pinning test class (supersedes Decision 4 of expected-artifacts-manifest-repair)

## Rationale

_(none)_

## Change log

- `2026-09-26T13:18:22.223244+00:00` — opened
- `2026-09-26T13:18:24.698597+00:00` — resolved (final_answer="Delete the override and the TestOverrideMirrorDeprecation pinning test class (supersedes Decision 4 of expected-artifacts-manifest-repair)")
