# Mission Specification: Upgrade dry-run reports the sequenced verdict a real run reaches

**Mission Branch**: `issue-6552-upgrade-dry-run-sequenced-verdict`
**Created**: 2026-10-31
**Status**: Draft
**Input**: User description: "Issue spec-kitty/spec-kitty#6552 — `upgrade: --dry-run reports a migration as 'not needed' when an earlier migration would have selected it`. Reproduce, then make the dry-run simulate the same sequenced view the real runner uses (one selection authority), and pin the disagreement with a test."

**Governing issue**: [#6552](https://github.com/spec-kitty/spec-kitty/issues/6552) (`priority:P3`, `usability`, `domain:upgrade`).

### Intent Summary (confirmed before this spec was written)

The operator named the issue and the intended shape: reproduce on current `main`, make the
dry run decide each migration on the sequenced view the real runner produces (one
sequencing decision, not a second authority), and pin the disagreement with a test.

- **Primary actor**: the operator running `spec-kitty upgrade --dry-run` before a real upgrade.
- **Trigger**: a project with two pending migrations where the earlier one rewrites state the
  later one's `detect()` reads.
- **Desired outcome**: the dry run's per-migration verdicts and `Migrations applied:` list
  name the work the real run then applies.
- **Invariant**: the dry run writes nothing — not to the project, not to the ledger, not to
  the clone-local partition — while the real run's behaviour stays byte-identical.
- **Boundary**: the decision belongs to the migration runner; the ledger stays the applied
  authority and `order_manifest.txt` stays the execution-order authority.

## Problem

`spec-kitty upgrade --dry-run` runs the same ordered migration loop as a real run, but
every `apply(dry_run=True)` returns without writing. A migration whose `detect()` reads
state that an *earlier migration in the same run* writes therefore sees the pre-run tree
in the dry run and the sequenced tree in the real run. The dry run reports it as
`not needed (project already in target state)` while the real run applies it, and the
`Migrations applied:` list differs between the two modes.

Measured on the reported pair (`3.2.6_gate_artifact_merge_drivers` rewrites
`merge.spec-kitty-issue-matrix.name`, which makes `3.2.6_issue_matrix_driver_repoint`
needed): the dry run printed `○ 3.2.6_issue_matrix_driver_repoint` plus
`! Migration 3.2.6_issue_matrix_driver_repoint not needed (project already in target state)`;
the real run printed `✓ 3.2.6_issue_matrix_driver_repoint`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The preview names the work the real run will do (Priority: P1)

An operator runs `spec-kitty upgrade --project --dry-run` before upgrading. The preview's
per-migration verdicts and `Migrations applied:` list name the same migrations the real run
then applies, including a migration that only becomes needed because an earlier migration
in the same run rewrote the state it detects.

**Why this priority**: The preview is the only forecast an operator gets before a
one-way upgrade, and a migration the dry run calls "already in target state" is
exactly the one whose absence from the forecast hides pending work.

**Independent Test**: On a project where the gate-artifact merge-driver migration is
pending and the repoint migration is pending-but-not-yet-detected, run the migration
runner with `dry_run=True` and, on an identical copy, with `dry_run=False`; assert the
two `migrations_applied` lists are equal and both contain the repoint migration.

**Acceptance Scenarios**:

1. **Given** a project where an earlier migration in the run will rewrite state a later
   migration's `detect()` reads, **When** the upgrade runs with `--dry-run`, **Then** the
   later migration is reported as applied (predicted), not as
   `not needed (project already in target state)`, and the predicted entry names the
   earlier migration.
2. **Given** the same project, **When** the upgrade runs for real, **Then** the applied
   list is unchanged from today's behaviour (the real run's sequencing already worked).
3. **Given** a dry run, **When** it completes, **Then** the project tree, the tracked
   ledger and the clone-local ledger are byte-identical to the pre-run state.

---

### User Story 2 - A dry-run skip no longer overclaims the project state (Priority: P2)

When a migration's `detect()` reads state written by a migration that does not declare the
relationship, the dry run cannot predict the verdict. It then stops asserting
`project already in target state` — a claim about the end of the run it has not simulated —
and says the migration is not needed *on the current tree*.

**Why this priority**: The misleading claim is the reported defect's operator-visible harm;
an honest limit beats a false certainty. The real-run wording stays as it is, because a real
run does reach the target state.

**Independent Test**: With an undeclared ordering pair, assert the dry-run skip warning says
"not needed on the current tree" and never "project already in target state"; assert the
real-run warning is unchanged.

**Acceptance Scenarios**:

1. **Given** an undeclared ordering dependency, **When** the upgrade runs with `--dry-run`,
   **Then** the skip warning says `not needed on the current tree` and the migration is
   listed as skipped.
2. **Given** the same project, **When** the upgrade runs for real, **Then** the skip
   warning keeps today's `not needed (project already in target state)` wording.

---

### Edge Cases

- **The declared predecessor was not applied in this run** (already settled in the ledger,
  or skipped itself): no prediction; the verdict is whatever `detect()` says. A dependency
  that is not part of this run's selection cannot change the tree.
- **The predecessor is applied but the dependent is not applicable here** (`can_apply`
  refuses): the prediction must honour `can_apply`, exactly as the real run's skip does.
- **The dependent's own `detect()` says needed**: the normal path runs; no prediction is
  consulted.
- **Discovery order**: the predecessor must be ordered before the dependent by
  `order_manifest.txt`; the declaration never reorders anything.
- **Unknown ids in a declaration** (a renamed or removed predecessor): ignored; a
  declaration never fails a run.
- **The dry run's worktree pass**: unchanged; worktree verdicts are per-worktree and are
  not part of the reported `Migrations applied:` list.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | One sequencing decision in the runner | As an operator, I want the dry run's per-migration verdict to come from one sequencing decision in the runner, so the preview cannot drift from the real run through a second code path. | High | Open | [build] | no — a do-nothing change leaves the dry run reporting `not needed (project already in target state)` |
| FR-002 | Declared detect-input predecessors | As a migration author, I want to declare the migrations whose writes my `detect()` reads, so the preview can sequence them without guessing. | High | Open | [build] | no — with no declaration the reported pair stays unpredictable |
| FR-003 | Predicted application for a declared dependent | As an operator, I want a migration whose declared predecessor is being applied in this run reported as applied, so `Migrations applied:` matches the real run. | High | Open | [build] | no — the reported pair's dry-run list is short by one entry today |
| FR-004 | Honest wording for an unpredicted skip | As an operator, I want an unpredicted dry-run skip to claim only the current tree, so a look-ahead claim never outruns the simulation. | Medium | Open | [build] | no — the dry run asserts target state it has not simulated |
| FR-005 | The reported 3.2.6 pair declares the relationship | As a maintainer, I want `3.2.6_issue_matrix_driver_repoint` to declare `3.2.6_gate_artifact_merge_drivers` as its detect-input predecessor, so the measured case is predicted. | High | Open | [build] | no — the pair is the reported reproduction |
| FR-006 | Parity witness on the production path | As a maintainer, I want a regression test that drives the real runner (and the CLI surface) end to end on the reported pair, so the parity claim is exercised, not assumed. | High | Open | [ratchet] | no — the test fails on today's tree |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | The dry run still writes nothing | After a dry run of the fixture project, the project tree (including `.git/config` and `.gitattributes`), the tracked ledger and the clone-local ledger hash identically to the pre-run snapshot. | Reliability | High | Open |
| NFR-002 | No project copy, no measurable slowdown | The prediction adds no filesystem copy and no extra `detect()`/`apply()` call: the per-migration work in a dry run stays O(1) in the number of declared dependencies (measured on the fixture: a dry run over the discovered set issues no additional migration `apply()`). | Performance | Medium | Open |
| NFR-003 | Complexity ceiling | The touched runner functions stay at or below the repository's cyclomatic ceiling of 15. | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Execution order stays in the manifest | `order_manifest.txt` remains the single execution-order authority (ADR 2026-10-17-1 §2); the new declaration is detect-input metadata for the preview only and never reorders the run. | Technical | High | Open |
| C-002 | Real-run behaviour is unchanged | A real (`dry_run=False`) upgrade keeps today's verdicts, warnings, writes and ledger records byte-for-byte; no migration's `detect()`/`apply()` body gains a branch on the new declaration. | Technical | High | Open |
| C-003 | The ledger stays the applied authority | `MigrationRegistry.get_applicable` and `migration_settled` remain the only selection authority; the prediction is a per-migration verdict, never a way to select a migration the ledger has not. | Technical | High | Open |
| C-004 | Scope is the main project loop | The worktree pass, `--plan-json` and the frozen `compat-planner.json` contract are out of scope; no new JSON field is added to a frozen contract. | Technical | Medium | Open |
| C-005 | Pre-existing reds are cited, not fixed | This mission does not attempt #6798, #6801, #6816 or #5927. | Business | Medium | Open |

### Key Entities

- **Migration declaration (`sequenced_after`)**: a class-level tuple of migration ids on
  `BaseMigration`; the migrations whose application, earlier in the same run, changes what
  this migration's `detect()` reads. Empty by default; never an ordering authority.
- **Predicted verdict**: a dry-run result for a migration whose declaration names a
  predecessor the same run reports applied. Status `applied`, with a change line naming the
  predecessor, so the operator can tell a prediction from a direct detection.
- **Sequenced view**: the state the real runner sees at the dependent's position in the
  order — the pre-run tree plus every applied migration before it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the fixture project reproducing #6552, the dry-run `Migrations applied:` list equals the real run's list (0 differing entries; today: 1) — [build] · no-op passable: no
- **SC-002**: The dry run of the fixture writes nothing: tree and both ledger partitions hash identically before and after (today: already true; pinned so the fix cannot trade honesty for writes) — [ratchet] · no-op passable: no
- **SC-003**: No dry-run skip warning on the fixture says `project already in target state` for a migration the same run's prediction covers, and an undeclared ordering pair reports `not needed on the current tree` — [build] · no-op passable: no
- **SC-004**: A real upgrade of the fixture produces the same applied set, ledger records and warnings as before the change (0 diffs) — [ratchet] · no-op passable: no
