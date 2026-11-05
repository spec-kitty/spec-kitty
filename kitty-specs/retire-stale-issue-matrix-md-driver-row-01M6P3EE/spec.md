# Mission Specification: Retire the stale `issue-matrix.md` merge-driver row

**Mission Branch**: `issue-7217-retire-stale-issue-matrix-md-driver-row`
**Created**: 2026-11-05
**Status**: Draft
**Input**: User description: "Issue spec-kitty/spec-kitty#7217 — `upgrade re-adds a stale issue-matrix.md merge-driver row to .gitattributes on every fresh clone`. Establish whether the driver is retired or re-added correctly, then fix it red-first."

**Governing issue**: [#7217](https://github.com/spec-kitty/spec-kitty/issues/7217) (`reliability`, `priority:P2`, `domain:upgrade`).
Split out of [#7173](https://github.com/spec-kitty/spec-kitty/issues/7173) ("Also in scope"); PR #7196 covers only that parent's worktree cleanup.

### Intent Summary (confirmed before this spec was written)

The operator named the issue, and asked for one question to be settled before either side is
changed: **is the driver wrong, or is the row wrong?**

**Answer (grounded below): the row is wrong; the driver stays.** `issue-matrix.md` is a legacy
read-only artifact, and the `spec-kitty-issue-matrix` driver merges the JSON `rows` array, so
mapping a Markdown table onto it was never right — it was only ever inert. What must be
"re-added correctly" is the *other* half of the same historical migration: the
`acceptance-matrix.json` row and driver config, which remain live and must survive the
retirement.

- **Primary actor**: the operator of a consumer repository (and of this repository) who runs
  `spec-kitty upgrade`.
- **Trigger**: the first upgrade on a fresh clone, or any later upgrade.
- **Desired outcome**: `.gitattributes` is unchanged by an upgrade that has nothing to do to
  it, and a project that already carries the stale row is healed.
- **Invariant**: both real gate-artifact rows keep their merge drivers
  (`acceptance-matrix.json`, `issue-matrix.json`); the row-aware driver is never lost.
- **Boundary**: the shipped migration modules stay byte-identical (DIRECTIVE_044); the fix is
  a supersession entry plus a successor migration, exactly as the issue proposes.

## Problem

`3.2.6_gate_artifact_merge_drivers` seeds two merge-driver rows, one of them
`kitty-specs/**/issue-matrix.md merge=spec-kitty-issue-matrix`. WP05
(`write-side-seam-matrix-tracer-01KYP3MH`, C-008) then moved the canonical artifact to
`issue-matrix.json`; `3.2.6_issue_matrix_driver_repoint` added the `.json` row **without**
removing the old one, and no code path writes (or reads) `issue-matrix.md` as a merge target
any more.

Measured on `origin/main` (`b4d1e918e2`) in a clean throwaway clone of this repository: the
first `spec-kitty upgrade` re-applied `3.2.6_gate_artifact_merge_drivers` and appended the
stale row, leaving ` M .gitattributes` — reproducing the issue exactly. The cause is
`clone_local_effect = True`: a fresh clone never carries the driver's `git config --local`
half, so `detect()` is True, the migration is re-selected and re-applied, and it re-appends
the row it wrote in 3.2.6.

Two consequences follow:

1. **The row is an orphan.** No declared driver matches it (`_MERGE_DRIVERS` declares only
   `kitty-specs/**/issue-matrix.json` for `spec-kitty-issue-matrix`), so
   `tests/architectural/test_merge_reconciliation_class_guard.py::test_declared_merge_drivers_are_registered_in_gitattributes`
   rejects it as drift.
2. **The workaround propagated it.** `init` now writes every line an upgrade seeds
   (`merge_attribute_seed_lines()`, #6416), including this inert one, so a freshly
   initialized consumer repository is *born* with the orphan row; only this repository's
   committed `.gitattributes` (edited by hand) lacks it, which is why the defect shows up
   here as "the upgrade dirties the tree".

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An upgrade leaves `.gitattributes` alone (Priority: P1)

An operator clones a repository and runs `spec-kitty upgrade`. The upgrade does its clone-local
work (driver config) but the tracked `.gitattributes` is byte-identical afterwards, and
`git status` is clean.

**Why this priority**: This is the reported defect: an upgrade that has nothing to do to a
tracked file must not modify it. It reds CI on a committed tree and trains operators to
`git checkout -- .gitattributes`.

**Independent Test**: On a committed project whose `.gitattributes` carries exactly the
canonical merge-driver lines, run `spec-kitty upgrade --yes`; assert the file's bytes and
`git status --porcelain` are unchanged, and that a second upgrade changes nothing either.

**Acceptance Scenarios**:

1. **Given** a committed project with the canonical `.gitattributes` and no `issue-matrix.md`
   row, **When** the upgrade runs, **Then** `.gitattributes` is byte-identical and the working
   tree is clean.
2. **Given** the same project, **When** the upgrade runs again, **Then** nothing changes (the
   clone-local reselect is idempotent, and the row is not re-added between runs).

---

### User Story 2 - A project that already carries the row is healed (Priority: P1)

A consumer repository that upgraded under 3.2.6 already has the stale row committed. An
upgrade removes exactly that row and touches no other line.

**Why this priority**: The row is already in consumer repositories' history; retiring it only
for fresh clones would leave the orphan everywhere else and keep failing the guard test for
them.

**Independent Test**: Seed a project with the stale row among the canonical rows, upgrade, and
assert the row is gone while every other line and its order are unchanged.

**Acceptance Scenarios**:

1. **Given** a project whose `.gitattributes` has the stale `.md` row, **When** the upgrade
   runs, **Then** the row is removed, nothing else in the file changes, and the removal is
   reported.
2. **Given** that project, **When** the upgrade runs again, **Then** the file is untouched (the
   removal is idempotent).

---

### User Story 3 - No driver is lost by the retirement (Priority: P1)

The retirement must not take the live gate-artifact drivers with it. After the upgrade, the
`acceptance-matrix.json` and `issue-matrix.json` rows are present in `.gitattributes` and both
`merge.spec-kitty-*` driver configs are installed, at their canonical names.

**Why this priority**: `3.2.6_gate_artifact_merge_drivers` is superseded as a whole, and its
acceptance-matrix half is the #2804 fix (a squash merge used to keep empty gate artifacts).
Superseding it without re-seeding that half would silently reintroduce #2804 for every
already-initialized repository that upgrades from before 3.2.6.

**Independent Test**: On a project with no gate-artifact state at all, upgrade; assert both
rows in `.gitattributes` and both `git config --local` driver entries with their canonical
names, and that `init` writes the same two rows.

**Acceptance Scenarios**:

1. **Given** a project with neither gate-artifact row, **When** the upgrade runs, **Then**
   `acceptance-matrix.json` and `issue-matrix.json` rows and both driver configs exist.
2. **Given** a fresh `init`, **When** its `.gitattributes` is read, **Then** it carries the two
   canonical rows and not the retired `.md` row.

---

### Edge Cases

- **Non-git project**: the seeding base warns and skips local config; the row removal still
  applies to the file (the row is a tracked-file concern).
- **`.gitattributes` absent**: the successor seeds the file; removal is a no-op.
- **Row present with surrounding whitespace**: the stale mapping is removed by its stripped
  form; no other line is touched, and no blank-line collapse happens.
- **The driver config name is the historical `filled-side merge`** (a project that ran the gate
  migration but not the repoint): the successor rewrites it to the canonical row-aware name.
- **`.md` file genuinely committed in an old mission**: nothing creates or merges it; the
  retirement is about the attribute row, not the file (legacy readers keep working).
- **An operator who wants the row**: none can want it — the pattern matches no artifact any
  code path writes, and the mapped driver parses JSON.
- **DIRECTIVE_044**: neither shipped migration module may be edited; only the supersession
  table and a new module change.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Supersede the stale writer | As an operator, I want the historical gate-artifact migration to stop re-applying on every clone, so a fresh clone's upgrade cannot append the retired row again. | High | Open | [build] | no — a do-nothing change leaves `3.2.6_gate_artifact_merge_drivers` selected and appending the row |
| FR-002 | Keep the live halves | As an operator, I want the successor to seed the `acceptance-matrix.json` and `issue-matrix.json` rows and both driver configs, so superseding the historical migration does not drop the #2804 fix. | High | Open | [build] | no — a successor that only removes the row loses the acceptance-matrix half for pre-3.2.6 upgraders |
| FR-003 | Remove the row where it was written | As an operator with the stale row already committed, I want an upgrade to remove exactly that row, so the orphan does not persist in consumer repositories. | High | Open | [build] | no — a do-nothing change leaves the row in place |
| FR-004 | Stop seeding it at init | As an operator of a new project, I want `init` to write only canonical rows, so a fresh project is not born with the orphan row. | High | Open | [build] | no — `merge_attribute_seed_lines()` still unions the historical migration's drivers while it is live |
| FR-005 | Retire the now-dead declaration | As a maintainer, I want the `SEQUENCED_AFTER` entry that pointed at the superseded migration removed, so no declaration claims a predecessor that can never apply. | Medium | Open | [build] | no — a dead declaration stays green only because nothing checks it |
| FR-006 | Pin the retirement | As a maintainer, I want a supersession-table test entry and a retirement pin, so a future edit cannot silently re-introduce the row or drop the successor. | Medium | Open | [ratchet] | no — the guard test fails today on a project holding the row |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Byte-level no-op | An upgrade on a project whose `.gitattributes` already lacks the row leaves the file's bytes unchanged; `git status --porcelain` is empty. | Reliability | High | Open |
| NFR-002 | Idempotent reselect | Two consecutive upgrades on the same project produce identical `.gitattributes` bytes and no repeated change report. | Reliability | High | Open |
| NFR-003 | No shipped-module drift | `m_3_2_6_gate_artifact_merge_drivers.py` and `m_3_2_6_issue_matrix_driver_repoint.py` keep their byte content, so no recorded `content_hash` drifts. | Maintainability | High | Open |
| NFR-004 | Bounded surface | The change touches one new migration module, the supersession table, the order manifest, the init seed docstring and tests; no new CLI flag, no new artifact. | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|--------|--------|
| C-001 | DIRECTIVE_044 | A shipped migration module is never edited; its bytes are its `content_hash`. The fix is a supersession entry plus a new module. | Technical | High | Open |
| C-002 | One canonical declaration | `_MERGE_DRIVERS` (`src/specify_cli/lanes/consolidation.py`) stays the single declaration of merge drivers; no `.md` pattern returns to it. | Technical | High | Open |
| C-003 | Manifest owns order | `order_manifest.txt` stays the single execution-order authority; the successor is listed there in its version slot. | Technical | High | Open |
| C-004 | Driver, not format | The `spec-kitty-issue-matrix` driver keeps merging `issue-matrix.json` rows; it is not repointed at Markdown. | Technical | High | Open |
| C-005 | No gate weakening | The architectural guard (`test_declared_merge_drivers_are_registered_in_gitattributes`) and the supersession table test keep every assertion they have today. | Process | High | Open |

### Key Entities

- **Retired row**: `kitty-specs/**/issue-matrix.md merge=spec-kitty-issue-matrix` — a
  `.gitattributes` line with no matching declared driver pattern and no artifact that any
  canonical path writes.
- **Successor migration**: `4.0.0rc8_retire_issue_matrix_md_row` — the one migration that
  replaces the superseded one; seeds the two live gate-artifact rows/configs and removes the
  retired row.
- **Supersession entry**: `SUPERSEDED_MIGRATIONS["3.2.6_gate_artifact_merge_drivers"] =
  "4.0.0rc8_retire_issue_matrix_md_row"` — the registry's declared no-op substitution.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A `spec-kitty upgrade` on a committed project with the canonical `.gitattributes` leaves the file byte-identical and `git status --porcelain` empty. — [build] · no-op passable: no
- **SC-002**: `grep -c "issue-matrix.md merge=" .gitattributes` is `0` after an upgrade on both a clean project and one seeded with the row, while the two canonical gate-artifact rows are present. — [build] · no-op passable: no
- **SC-003**: A second upgrade performs no change (same bytes, no repeated change line). — [ratchet] · no-op passable: no
- **SC-004**: The targeted upgrade/init suites plus the architectural merge-driver guard pass, with no assertion removed or relaxed. — [ratchet] · no-op passable: no
