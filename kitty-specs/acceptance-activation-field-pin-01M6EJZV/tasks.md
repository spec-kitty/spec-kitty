# Tasks — Acceptance test measures the activation field set, not a count

**Mission**: `acceptance-activation-field-pin-01M6EJZV`
**Branch**: `issue-7038-acceptance-activation-field-pin`
**Input**: `spec.md`, `plan.md`, `research.md`

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Replace the model-derived field list and the hard-coded `len(fields) == 10` with the vocabulary authority | WP01 | no |
| T002 | Keep the behavioural load (model validation + real `charter context` CLI) and add a non-vacuity guard | WP01 | no |
| T003 | Rename the test and re-docstring it to state the property and point at the parity gate | WP01 | no |
| T004 | Prove red-before/green-after and run the adjacent vocabulary and model tests | WP01 | no |
| T005 | Record the fix in the PR changelog fragment and PR body | WP01 | no |

## Work Packages

### WP01 — Authority-sourced activation field set in the acceptance test

- **Summary**: Remove the stale hand-restated activation-field count from
  `tests/acceptance/test_unmigrated_cli_still_runs.py`. The test reads its field set from
  `charter.activation.pack_manager.ACTIVATION_YAML_KEYS`, keeps building and validating a
  `charter.yaml` document that carries every writable activation key, keeps the real-CLI load,
  asserts the vocabulary is non-empty, and is renamed to state the property. No `src/` change.
- **Priority**: P1 (the only work package; the file is red on `main` today)
- **Independent test**: the renamed test passes on the branch and fails if the authority carries a
  key the model does not declare (`extra_forbidden`); the vocabulary parity gate and the model
  tests stay green.
- **Included subtasks**: T001, T002, T003, T004, T005
- **Implementation sketch**: lazy authority import helper → rewrite the test body → run the target
  test red/green → run the two adjacent test modules → changelog fragment + PR body.
- **Parallel opportunities**: none (single file, single test).
- **Dependencies**: none.
- **Risks**: a vacuous loop if the authority were empty (guarded); duplicating the parity gate
  (explicitly avoided); reintroducing `activated_assets` (must not).
