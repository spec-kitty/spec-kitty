# Work Packages: Retire the stale `issue-matrix.md` merge-driver row

**Inputs**: Design documents from `kitty-specs/retire-stale-issue-matrix-md-driver-row-01M6P3EE/`
**Prerequisites**: spec.md, research.md, plan.md
**Governing issue**: [#7217](https://github.com/spec-kitty/spec-kitty/issues/7217)

**Organization**: Three work packages. WP01 is the retirement itself and its red-first proof;
WP02 is the follow-through the retirement forces on the `init` seed, the dead sequencing
declaration and the two dry-run test modules; WP03 is the operator-facing changelog, the
issue verdict and the verification sweep.

## Subtask Format: `[Txxx] [P?] Description`

- **[P]** marks a subtask that can proceed in parallel (different files/components).
- Subtasks are reference rows; completion is recorded with
  `spec-kitty agent tasks mark-status Txxx --status done`.

## Path Conventions

Single project: `src/`, `tests/`, `docs/`.

---

## Work Package WP01: Retire the row, keep the drivers (Priority: P0)

**Goal**: `3.2.6_gate_artifact_merge_drivers` is superseded, and a `4.0.0rc8` successor seeds the
two live gate-artifact rows/configs and removes the retired `.md` row idempotently, so a fresh
clone's upgrade cannot re-append it.
**Independent Test**: On a committed project with the canonical `.gitattributes`, `spec-kitty
upgrade --yes` leaves the file byte-identical and `git status` clean; a project seeded with the
row has exactly that row removed and both live rows/drivers present.
**Prompt**: `tasks/WP01-retire-the-row.md`
**Requirement Refs**: FR-001, FR-002, FR-003, FR-006, NFR-001, NFR-002, NFR-003, C-001, C-002, C-003, C-004, C-005

### Included Subtasks

- T001 Red-first: the new retirement test module fails on the pre-fix tree
- T002 `SUPERSEDED_MIGRATIONS` entry for `3.2.6_gate_artifact_merge_drivers`
- T003 The successor migration `4.0.0rc8_retire_issue_matrix_md_row`
- T004 The successor's `order_manifest.txt` slot
- T005 Extend the supersession-table test's `SHIPPED_SUPERSEDED`
- T006 Targeted suites, ruff, format, mypy

### Implementation Notes

- The successor subclasses `MergeDriverSeedingMigration` so it reuses the idempotent seeding of
  its `drivers`; it overrides only `detect()` (adds "the retired row is present") and
  `apply()` (seeds, then removes the retired row and reports it).
- Removal is line-exact (stripped comparison of the one retired entry) and never rewrites,
  re-sorts or re-blanks the rest of the file.
- `clone_local_effect = True` is inherited and must stay: the driver config half is
  clone-local, so the successor must re-apply per clone.
- Do not touch the two 3.2.6 modules, `_merge_driver_seeding.py`, or `_MERGE_DRIVERS`.

### Dependencies

- None (starting package).

### Risks & Mitigations

- Dropping the acceptance-matrix half → T001's fixture starts with no gate-artifact state and
  asserts both live rows and both configs afterwards.
- A `.gitattributes` rewrite that reorders lines → the healing test diffs line by line.

---

## Work Package WP02: The follow-through the retirement forces (Priority: P1)

**Goal**: `init` stops writing the retired line (with no new special case), the dead
`SEQUENCED_AFTER` declaration goes with its writer, and the dry-run prediction proofs keep every
assertion on a same-shaped pair.
**Independent Test**: `spec-kitty init` then `spec-kitty upgrade` on a committed project leaves
tree and bytes unchanged; the two dry-run modules pass on the re-anchored pair; the declaration
audit passes with no shipped declaration left.
**Prompt**: `tasks/WP02-follow-through.md`
**Requirement Refs**: FR-004, FR-005, NFR-001, C-005

### Included Subtasks

- T001 `merge_attribute_seed_lines()` docstring: the union no longer needs the historical case
- T002 Invert the `init` seed test (`test_init_then_upgrade_is_noop.py`)
- T003 Remove the dead `SEQUENCED_AFTER` entry and its comment; update the `sequenced_after`
  example in `migrations/README.md`
- T004 Re-anchor `tests/upgrade/test_dry_run_sequenced_verdict.py` on the synthetic declared pair
- T005 Re-anchor `tests/upgrade/test_dry_run_sequenced_verdict_cli.py` the same way
- T006 Targeted suites, ruff, format

### Implementation Notes

- The `init` seed's union stays (it is still what keeps a *live* seeding migration's line from
  dirtying the first upgrade); only the docstring's historical justification changes, because
  the superseded module is no longer a live `MergeDriverSeedingMigration`.
- The dry-run modules pin the prediction *mechanism*; the retired ids were only its reported
  example. Re-anchor on the synthetic pair already defined in the runner module, and pin
  explicitly that the retired declaration is gone.
- Do not delete any assertion; the audit still enforces "every declared predecessor is a
  registered, earlier-ordered migration" for any future declaration.

### Dependencies

- Depends on WP01 (the supersession entry is what makes the init line disappear and the
  declaration dead).

### Risks & Mitigations

- A test that passes vacuously after re-anchoring → keep the existing fixture preconditions and
  the "the real run must write" positive control.

---

## Work Package WP03: Changelog, issue verdict, verification sweep (Priority: P2)

**Goal**: The change is documented for operators, #7217 carries a terminal verdict with
evidence, and the touched surfaces are verified together.
**Independent Test**: the changelog fragment passes `check_changelog_style` and
`check_spelling`; the targeted suites pass on the branch tip; the issue matrix row states
`fixed` with the test and PR evidence.
**Prompt**: `tasks/WP03-changelog-and-verification.md`
**Requirement Refs**: FR-006, NFR-004, SC-004

### Included Subtasks

- T001 The changelog fragment (`docs/changelog/unreleased/<pr>.fixed.md`) with the before/after
- T002 Issue-matrix verdict for #7217 with evidence
- T003 Verification sweep (targeted suites, docs/changelog style checks, ruff, mypy)
- T004 Confirm no docs page states the retired row as current behavior

### Dependencies

- Depends on WP01 and WP02 (needs the PR number for the fragment name and the final behaviour).

### Risks & Mitigations

- Editing `docs/changelog/CHANGELOG.md` → forbidden since #6988; fragments only.
- A docs page that documents the retired row → grep for `issue-matrix.md merge` under `docs/`
  and fix only what states current behaviour (the historical changelog entry stays).
