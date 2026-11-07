---
work_package_id: WP02
title: The follow-through the retirement forces
dependencies:
- WP01
requirement_refs:
- FR-004
- FR-005
- NFR-001
- C-005
planning_base_branch: issue-7217-retire-stale-issue-matrix-md-driver-row
merge_target_branch: issue-7217-retire-stale-issue-matrix-md-driver-row
branch_strategy: Planning artifacts for this mission were generated on issue-7217-retire-stale-issue-matrix-md-driver-row. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into issue-7217-retire-stale-issue-matrix-md-driver-row unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-retire-stale-issue-matrix-md-driver-row-01M6P3EE
base_commit: 0a0ae6bccac0bbd0aef4fbcbb930bde2620e7e44
created_at: '2026-11-05T15:32:24.522024+00:00'
subtasks:
- T001
- T002
- T003
- T004
- T005
- T006
phase: Phase 2 - Follow-through
history:
- at: '2026-11-05T15:10:00+00:00'
  actor: system
  action: Prompt generated via /spec-kitty.tasks
agent_profile: python-pedro
authoritative_surface: tests/upgrade/
create_intent: []
execution_mode: code_change
owned_files:
- src/specify_cli/upgrade/init_seed.py
- src/specify_cli/upgrade/runner.py
- src/specify_cli/upgrade/migrations/README.md
- tests/init/test_init_then_upgrade_is_noop.py
- tests/upgrade/test_dry_run_sequenced_verdict.py
- tests/upgrade/test_dry_run_sequenced_verdict_cli.py
role: implementer
tags: []
task_type: implement
tracker_refs:
- '7217'
---

# Work Package Prompt: WP02 – The follow-through the retirement forces

## ⚡ Do This First: Load Agent Profile

- **Profile**: `python-pedro`
- **Role**: `implementer`

## Objectives & Success Criteria

Once `3.2.6_gate_artifact_merge_drivers` is a superseded no-op (WP01), three consequences must
be carried through instead of left as silent drift:

1. the `init` seed no longer writes the retired line — and the docstring must stop justifying a
   workaround that no longer exists (#6416);
2. `SEQUENCED_AFTER`'s only entry declared `3.2.6_gate_artifact_merge_drivers` as the
   predecessor of `3.2.6_issue_matrix_driver_repoint`; that predecessor can never apply now, so
   the declaration is dead and must go;
3. the two dry-run test modules used that pair as their "reported pair". They pin the prediction
   *mechanism*, so re-anchor them on the same-shaped synthetic pair rather than deleting any
   assertion.

Done when:

- `spec-kitty init` writes the two canonical gate-artifact rows and **not** the retired `.md`
  row; `init` then `upgrade` on a committed project leaves the tree and bytes unchanged.
- No shipped migration declares a predecessor that can never apply.
- Both dry-run modules pass with every existing assertion intact, and a new pin states that the
  retired declaration is gone.

## Context & Constraints

- Issue: <https://github.com/spec-kitty/spec-kitty/issues/7217>
- Plan: `kitty-specs/retire-stale-issue-matrix-md-driver-row-01M6P3EE/plan.md` (D-004)
- Research: `kitty-specs/retire-stale-issue-matrix-md-driver-row-01M6P3EE/research.md`
  ("Blast radius survey")

Read before editing:

- `src/specify_cli/upgrade/init_seed.py` — `merge_attribute_seed_lines()` and its docstring.
- `src/specify_cli/upgrade/runner.py` — `SEQUENCED_AFTER`,
  `declared_predecessors`, `sequenced_predecessors` and the docstrings around them.
- `src/specify_cli/upgrade/migrations/README.md` — the `sequenced_after` section (its example
  names the retired id).
- `tests/upgrade/test_dry_run_sequenced_verdict.py` — `_pair_project`, `_SEEDED_ATTRIBUTES`,
  `_SEEDED_CONFIG`, the U1 tests and the declaration audit; the synthetic `_WritesMarker` /
  `_DeclaredReadsMarker` / `_DeclaredReadsMarker` pair already in the file is the anchor.
- `tests/upgrade/test_dry_run_sequenced_verdict_cli.py` — imports `_pair_project`, `_copy`,
  `_tree_digest` from the module above and drives the real `upgrade` command.

Constraints:

- Do not delete, skip or weaken an assertion. Re-anchoring changes the fixture, not the proof.
- The `init` seed's union across live seeding migrations stays: it is what keeps a *live*
  migration's `.gitattributes` line from dirtying the first upgrade. Only the historical
  justification in the docstring goes.
- `order_manifest.txt` remains the ordering authority; a declaration never reorders.
- The successor's `drivers` are the only source of its rows — do not duplicate the line lists.

## Branch Strategy

- Single checkout on `issue-7217-retire-stale-issue-matrix-md-driver-row`.

## Subtasks & Detailed Guidance

### Subtask T001 – `init` seed docstring

- **Steps**: In `merge_attribute_seed_lines()`, rewrite the docstring paragraph that explains
  the historical `issue-matrix.md` line: the union still covers every *live* seeding migration,
  and the retired line is now absent because its writer is superseded, not because a caller
  special-cases it. Keep the mechanism untouched.
- **Files**: `src/specify_cli/upgrade/init_seed.py`

### Subtask T002 – Invert the `init` seed test

- **Steps**: In `tests/init/test_init_then_upgrade_is_noop.py`, replace
  `test_init_writes_the_legacy_issue_matrix_line_an_upgrade_seeds` with a test asserting `init`
  does **not** write `kitty-specs/**/issue-matrix.md merge=spec-kitty-issue-matrix` **and** that
  the two canonical gate-artifact rows are present in the same file (same-fixture positive
  control). Update the module docstring (it currently explains the workaround as the fix).
- **Files**: `tests/init/test_init_then_upgrade_is_noop.py`

### Subtask T003 – Remove the dead declaration

- **Steps**: Delete the `3.2.6_issue_matrix_driver_repoint` entry from `SEQUENCED_AFTER` and its
  explanatory comment, keeping the mapping + `declared_predecessors` mechanism for future
  declarations (update the module comment to say the table is empty by design after #7217). In
  `migrations/README.md`, replace the example's retired id with a neutral placeholder and add one
  line: a declaration whose predecessor is superseded can never fire, so retire it with the
  writer.
- **Files**: `src/specify_cli/upgrade/runner.py`, `src/specify_cli/upgrade/migrations/README.md`

### Subtask T004 – Re-anchor the runner-level dry-run module

- **Steps**: In `tests/upgrade/test_dry_run_sequenced_verdict.py`, replace the real-pair fixtures
  (`_pair_project`, `_SEEDED_ATTRIBUTES`, `_SEEDED_CONFIG`, `_GATE`, `_REPOINT` and the imports
  of the two 3.2.6 classes) with the synthetic declared pair already defined in the module
  (`_WritesMarker` → `_DeclaredReadsMarker`), keeping every assertion: parity between dry and
  real runs, the named prediction line, the no-writes digest, and the real-run positive control.
  Update the module docstring to record that the reported pair was
  `3.2.6_gate_artifact_merge_drivers → 3.2.6_issue_matrix_driver_repoint` and that #7217 retired
  it (so the same shape rides the synthetic pair). In the declaration audit, keep the
  registered/earlier invariant loop and add a pin that no shipped migration declares a
  predecessor (the retired one is gone), with a comment telling the next author to re-anchor the
  audit when a real declaration lands.
- **Files**: `tests/upgrade/test_dry_run_sequenced_verdict.py`
- **Notes**: keep the fixture-precondition assertions (`detect()` True before the run, False
  after) so a fixture drift fails loudly.

### Subtask T005 – Re-anchor the CLI witness

- **Steps**: In `tests/upgrade/test_dry_run_sequenced_verdict_cli.py`, use the same synthetic
  pair (import the shared fixture helpers so the two proofs cannot drift), pass an explicit
  `--target 9.9.9` (the synthetic pair's target version exceeds the package version, so the
  default target would exclude it), and keep all three assertions: the rendered prediction under
  the dry-run heading with its `would apply after`, the verbose preview agreeing, and the real
  run listing the migration without a prediction.
- **Files**: `tests/upgrade/test_dry_run_sequenced_verdict_cli.py`

### Subtask T006 – Verification

- `uv run pytest tests/upgrade/test_dry_run_sequenced_verdict.py tests/upgrade/test_dry_run_sequenced_verdict_cli.py -q`
- `uv run pytest tests/init/test_init_then_upgrade_is_noop.py tests/init/test_init_in_existing_repo.py tests/agent/test_init_command.py -q`
- `uv run ruff check src/specify_cli/upgrade tests/upgrade tests/init`
- `uv run ruff format --check --force-exclude <touched files>`

## Test Strategy

The `init`-then-`upgrade` test is the end-to-end positive control for FR-004 (it asserts the
whole tree is unchanged, so the inverted row assertion cannot pass by the file being untouched
for an unrelated reason). The dry-run re-anchor keeps the same assertions on a shape that still
exists in the codebase; the added audit pin makes the retirement explicit rather than silent.

## Risks & Mitigations

- **A weakened dry-run proof** → every assertion from the pre-change modules must still be
  present; only ids and fixture construction change.
- **`init` writes nothing at all** (over-correction) → the inverted test asserts the two canonical
  rows are present in the same file.
- **The audit becomes vacuous** → the new pin asserts the retired declaration is gone and the
  loop still enforces the invariant for any future declaration.

## Review Guidance

- Does `init` still seed every live seeding migration's `.gitattributes` line?
- Is the audit still capable of failing (registered + earlier-ordered predecessor)?
- Do the dry-run modules still prove dry/real parity, the named prediction, and no writes?
- Is the `--target` in the CLI witness justified by the synthetic pair's version?

## Progress & Status

Record subtask completion with `spec-kitty agent tasks mark-status T00x --status done`.
