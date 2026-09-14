# Decision Moment `01M2FXNHWVW9P88MSYN6RJQR3H`

- **Mission:** `sonar-per-pr-coverage-reuse-01M2FR32`
- **Origin flow:** `plan`
- **Slot key:** `plan.security.source-tree-delivery`
- **Input key:** `source_tree_delivery`
- **Status:** `resolved`
- **Created:** `2026-09-14T12:18:30.427264+00:00`
- **Resolved:** `2026-09-14T12:21:43.530073+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How does the PR source tree reach the scanner without letting the change under review control the analysis?

## Options

- Sparse trusted checkout + pinned -D args
- Restore config from trusted ref after checkout
- Other

## Final answer

Trusted default-branch checkout stays the working directory (diff-cover depends on it). The validated tested_sha is fetched into a separate subdirectory and referenced via sonar.projectBaseDir/sources; EVERY sonar.* setting is passed as an explicit -D argument resolved from the trusted tree, never read from the PR's sonar-project.properties. Satisfies FR-012 and NFR-008 together.

## Rationale

_(none)_

## Change log

- `2026-09-14T12:18:30.427264+00:00` — opened
- `2026-09-14T12:21:43.530073+00:00` — resolved (final_answer="Trusted default-branch checkout stays the working directory (diff-cover depends on it). The validated tested_sha is fetched into a separate subdirectory and referenced via sonar.projectBaseDir/sources; EVERY sonar.* setting is passed as an explicit -D argument resolved from the trusted tree, never read from the PR's sonar-project.properties. Satisfies FR-012 and NFR-008 together.")
