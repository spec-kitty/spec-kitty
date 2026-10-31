# Mission Specification: Repair historical sweep-created mission overrides

**Mission Branch**: `repair-historical-sweep-mission-overrides-01M68ZHQ`
**Created**: 2026-10-31
**Status**: Draft
**Input**: User description: "spec-kitty/spec-kitty#6548 — `upgrade: verify and repair historical sweep-created mission overrides outside the shipped #5280 repair`. Guided scope (Batch 6, agent S7): reproduce the residual historical override shape on the current baseline, then verify-and-repair it with a **new** corrective migration (shipped migration bodies stay frozen, DIRECTIVE_044 — `2.0.7_fix_stale_overrides` is not edited in place), under the existing ownership guard."

## Problem

An older build's `2.0.6_consistency_sweep` classified every file under
`.kittify/missions/<mission>/` as CUSTOMIZED and moved it into
`.kittify/overrides/missions/<mission>/` — including files the package ships, and files
byte-identical to the shipped copy. The counterpart lookup missed the shipped file because it
joined a second `missions/` segment onto an asset root that already ends in `missions/`
(`_find_package_counterpart` in `runtime/migrate.py`).

The new-sweep path is fixed: `_find_package_counterpart` now strips the leading `missions/`
before comparing, so a *future* classification run compares against the right shipped file
(the first, ticked acceptance item of the issue). Two things it does not cover are what this
issue retains:

1. `2.0.7_fix_stale_overrides` — the migration whose whole job is to remove overrides that a
   sweep created — still uses the old two joins on a `rel` that starts with `missions/`, so it
   reports "not needed" even for a byte-identical override. It is a shipped migration body and
   must not be edited (DIRECTIVE_044).
2. `4.0.0rc8_retire_stale_mission_template_forks` repairs 15 named documentation/research
   template fork files. An override a sweep created for `software-dev` — or any mission file
   the package ships that is not one of those 15 names — is still read at resolution tier 1 and
   silently shadows the shipped file.

On this baseline a project that already carries such an override keeps it across
`spec-kitty upgrade`, and `resolve_template` keeps answering `OVERRIDE`. Witnessed on
`dfe9efb0e8` with a project at `4.0.0rc8` holding
`.kittify/overrides/missions/software-dev/templates/spec-template.md` (byte-identical to
`packs/built-in/missions/software-dev/templates/spec-template.md`) and a deliberately
outdated `plan-template.md`:

```text
$ spec-kitty upgrade --project --yes          # 4.0.0rc8 -> 4.0.0rc8, exit 0
  ! Migration 2.0.7_fix_stale_overrides not needed (project already in target state)
  ! Migration 4.0.0rc8_retire_stale_mission_template_forks not needed (project already in target state)
$ find .kittify/overrides -type f
.kittify/overrides/missions/software-dev/templates/plan-template.md
.kittify/overrides/missions/software-dev/templates/spec-template.md
spec-template.md -> OVERRIDE .kittify/overrides/missions/software-dev/templates/spec-template.md
plan-template.md -> OVERRIDE .kittify/overrides/missions/software-dev/templates/plan-template.md
```

The migration ledger records both shipped steps as settled (`success`/`skipped`), so no future
upgrade revisits them. The override is permanent until a human edits the project by hand.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An upgrade repairs a sweep-created override that is the shipped file (Priority: P1)

A maintainer upgrades a long-lived project that an older sweep left with
`.kittify/overrides/missions/software-dev/templates/spec-template.md`, byte-identical to the
template Spec Kitty ships. `spec-kitty upgrade` removes that override and says so, and from then
on `resolve_template` answers from the package instead of the override tier, so a later pack
update is actually seen.

**Why this priority**: This is the issue's headline residual — a shipped file the tool itself
misplaced silently outranks every future pack update. Removal is safe only because the bytes
are proven identical, which is the one case the ownership guard authorizes.

**Independent Test**: Build a project at `4.0.0rc8` carrying a byte-identical override, run the
real `spec-kitty upgrade`, and assert the file is gone, the change is named in the output, and
`resolve_template` reports a non-`OVERRIDE` tier for both before and after.

**Acceptance Scenarios**:

1. **Given** a project whose `.kittify/overrides/missions/software-dev/templates/spec-template.md`
   is byte-identical to the shipped template, **When** `spec-kitty upgrade` runs, **Then** the
   override is removed and `resolve_template("spec-template.md", ..., "software-dev")` no longer
   answers `OVERRIDE`.
2. **Given** the same project, **When** the upgrade finishes, **Then** its output names the
   removed file, so the operator can see what changed and commit it.
3. **Given** the repaired project, **When** `spec-kitty upgrade` runs again, **Then** nothing else
   changes (the repair is a no-op and reports not-needed).

---

### User Story 2 - A differing override is preserved and named, never deleted (Priority: P1)

A maintainer's project also has an override that differs from the shipped file — the sweep moved
it, but its bytes might be their own edit, or an outdated default. Under #4961 differing bytes
cannot be proven package-owned, so the upgrade keeps the file exactly as it is and names it in a
warning: this override shadows the shipped file, and it is the operator's call.

**Why this priority**: The repair must not trade one silent shadowing for silent data loss. The
ownership guard's answer for unprovable bytes is preserve-and-name, and that is the answer this
issue asks for.

**Independent Test**: Plant a differing override, run the real `spec-kitty upgrade`, and assert
the bytes are unchanged, the file is named in the warnings, and the resolution tier is still
`OVERRIDE` (unchanged) — the positive control that the removal in Story 1 was not a blanket
delete of the directory.

**Acceptance Scenarios**:

1. **Given** an override whose bytes differ from the shipped counterpart, **When** the upgrade
   runs, **Then** the file is byte-for-byte unchanged and is named in the upgrade warnings.
2. **Given** both an identical and a differing override in one project, **When** the upgrade runs,
   **Then** only the identical one is removed, in a single step.
3. **Given** an override with no shipped counterpart at all (a custom mission, or a file the
   package does not ship at that path), **When** the upgrade runs, **Then** the file is not read
   for comparison, not named, and not touched.

---

### User Story 3 - One path mapping owns "which shipped file is this?" (Priority: P2)

A maintainer reads `runtime/migrate.py` and the repair migration and sees the same
`missions/<type>/<rest>` → `<package>/<type>/<rest>` mapping in one place, so the two cannot drift
into the two wrong joins that caused this issue.

**Why this priority**: The issue's own suggested fix asks for a single helper "used by both
modules [to] keep them from drifting again". Without it, the next repair writes the third copy of
the join.

**Independent Test**: Import the single helper, assert it maps a nested mission path to the
package file and refuses everything else; assert the classifier and the migration both resolve
through it (a change to the mapping moves both).

**Acceptance Scenarios**:

1. **Given** `rel = missions/software-dev/templates/spec-template.md` and the package missions
   root, **When** the helper is called, **Then** it returns
   `<package>/software-dev/templates/spec-template.md`.
2. **Given** a flat `templates/spec-template.md` (the pre-2.x layout) or a path with no shipped
   counterpart, **When** the helper is called, **Then** it returns `None` and the caller keeps
   its existing fallback joins.

---

### Edge Cases

- The override tree is a symlink, or a component of `.kittify/overrides/missions` is a symlink or
  not a directory: the scan refuses, warns, and changes nothing — it never follows the link outside
  the project.
- An individual override file is a symlink: it is skipped and named; nothing outside the project is
  read or removed.
- An unreadable override file: fail closed — preserved (never removed), the error is reported on
  the result.
- `.kittify/overrides/missions/<type>/` exists but is empty (a previous repair removed its files):
  no candidates, no directory is removed, nothing is reported.
- The package asset root cannot be located: the step refuses (a visible skip), rather than
  believing every override is custom.
- Two missions (`software-dev` and a custom `erp`) under `overrides/missions/`: the shipped
  mission's files are repaired on their own mission-relative path; `erp` has no counterpart and is
  untouched.
- Windows line endings: the comparison is exact bytes, matching `classify_asset` and `2.0.7`. A
  CRLF working-tree copy of a shipped LF file therefore reads as `differs`: it is preserved and
  named, never deleted, and a test pins that outcome. Folding CRLF would delete bytes the guard's
  canonical prover cannot prove, and would ask a different question than the classifier beside it.
- A project that already ran `4.0.0rc8_retire_stale_mission_template_forks`: its `migrate ledger`
  records stay; this migration is a separate id and runs independently.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Identical historical override removed | As a maintainer, I want `spec-kitty upgrade` to remove a sweep-created override that is byte-identical to the shipped file so that the shipped template stops being shadowed. | High | Open | [build] | no |
| FR-002 | Differing override preserved and named | As a maintainer, I want an override whose bytes differ kept exactly as it is and named in the upgrade output so that an unprovable file is never deleted and I decide. | High | Open | [build] | no |
| FR-003 | Single mapping helper | As a maintainer, I want one helper that maps a project mission path onto the shipped mission tree, used by both the classifier and the repair step, so the two joins that caused #6548 cannot come back. | High | Open | [build] | no |
| FR-004 | Removal only through the ownership guard | As a maintainer, I want every removal to go through `guard_destructive_removal` with a byte-identity prover that ignores the version marker so that no marker text and no name alone can authorize a delete. | High | Open | [ratchet] | no — positive control is FR-001 on the same fixture |
| FR-005 | No counterpart, no touch | As a maintainer, I want overrides with no shipped counterpart (custom missions, extra files) to be neither compared nor named nor touched so that genuine customisations stay invisible to the repair. | Medium | Open | [build] | no |
| FR-006 | Idempotent and ledger-recorded | As a maintainer, I want the repair recorded in the migration ledger and a second upgrade to change nothing so that it behaves like every other upgrade step. | Medium | Open | [build] | no |
| FR-007 | Symlink and directory safety | As a maintainer, I want a symlinked override or override tree refused with a warning and no directory created or removed so that the repair cannot reach outside the project. | Medium | Open | [ratchet] | no — paired with FR-001 on the same fixture |
| FR-008 | Frozen shipped migrations | As a maintainer, I want `2.0.7_fix_stale_overrides` and the other shipped migration bodies left byte-identical, with the repair delivered as a new migration id so that the ledger's drift audit stays clean (DIRECTIVE_044). | High | Open | [ratchet] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Bounded work | The repair reads only files under `.kittify/overrides/missions/**` and their shipped counterparts: no history walk, no network, no scan of `.kittify/missions/` or the global runtime home. | Performance | Medium | Open |
| NFR-002 | Fail closed | An unreadable override, an unresolvable package root, or a refused directory never results in a removal; each is reported on the migration result (error/warning) and the run continues. | Reliability | High | Open |
| NFR-003 | No new write surface | The step writes nothing except the guarded removal (and the migration ledger record the runner already writes); it creates no directory, writes no file, and does not rewrite an override. | Technical | High | Open |
| NFR-004 | Fast-tier test cost | The new unit tests stay in the fast tier; the one CLI-level test is marked integration and must complete in under 30 seconds on CI. | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | New migration id only | Do not edit `m_2_0_7_fix_stale_overrides.py`, `m_4_0_0rc8_retire_stale_mission_template_forks.py`, or any other shipped migration body; deliver a new module registered in `order_manifest.txt` (DIRECTIVE_044). | Technical | High | Open |
| C-002 | No resolver change | Resolution tier order, `resolve_template`/`resolve_mission` and the legacy nudge stay exactly as they are; the fix is the repair of the files, not the precedence. | Technical | High | Open |
| C-003 | No new sweep behaviour | Do not re-implement or re-tune the already-delivered `_find_package_counterpart` fix beyond routing it through the shared helper. | Technical | High | Open |
| C-004 | Scope is overrides only | Repair only `.kittify/overrides/missions/**`. `.kittify/missions/**` (legacy copies) and `.kittify/scripts/**` are out of scope; the classifier already handles the former and the flat-layout `2.0.7` handles the latter. | Technical | Medium | Open |

### Key Entities

- **Historical sweep override**: a file under `.kittify/overrides/missions/<type>/<rest>` that an
  older `2.0.6_consistency_sweep` moved out of `.kittify/missions/<type>/<rest>`.
- **Shipped counterpart**: the file the package ships at `<package missions root>/<type>/<rest>`;
  the only thing that can prove an override is package-owned.
- **Provenance verdict**: `identical` (bytes proven equal to the shipped counterpart → removable),
  `differs` (unprovable → preserved and named), or `no counterpart` (a genuine customisation →
  untouched).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the reproduced project (a `4.0.0rc8` project with a byte-identical and a differing
  `software-dev` template override), one `spec-kitty upgrade` leaves exactly one file under
  `.kittify/overrides/`: the differing one, byte-identical to its pre-upgrade content.
  — [build] · no-op passable: no
- **SC-002**: After that upgrade, `resolve_template` reports a non-`OVERRIDE` tier for the removed
  name and still `OVERRIDE` for the kept one — before/after tier recorded in the test.
  — [build] · no-op passable: no
- **SC-003**: Zero shipped migration modules change bytes in this diff (`git diff --stat` over
  `src/specify_cli/upgrade/migrations/m_2_0_7*` and `m_4_0_0rc8_retire_*` is empty), and the new id
  appears once in `order_manifest.txt`. — [ratchet] · no-op passable: no
- **SC-004**: The repair is idempotent: a second `apply()` on the repaired project makes zero
  changes and removes nothing — asserted at the migration seam, plus the CLI re-run reporting
  not-needed. — [build] · no-op passable: no
- **SC-005**: `spec-kitty migrate ledger` lists the new step in manifest order with its state, and
  a project that has run it reads it as already in place. — [build] · no-op passable: no

## Out of Scope

- The already-delivered new-sweep classification fix in `runtime/migrate.py` (#6548's first ticked
  item) — this mission only routes the mapping through a shared helper.
- The `docs/`-side "which overrides shadow a shipped file" doctor finding — the issue offers a
  migration *or* a doctor finding; this mission delivers the migration, and the naming lives in the
  upgrade warning.
- Repairing `.kittify/missions/**` legacy copies or the `.kittify/scripts/**` flat layout.
- Deleting or rewriting an override the package cannot prove; #4961 rules that out.

## Traceability

| Source | Requirement |
|--------|-------------|
| #6548 "Routine resolution / remaining acceptance" item 3 (reproduce the residual) | FR-001, FR-002, SC-001, SC-002 |
| #6548 remaining acceptance item 4 (new corrective repair, frozen bodies, name unproven) | FR-001, FR-002, FR-004, FR-008 |
| #6548 "Suggested Fix" (shared path mapping) | FR-003 |
| #4961 (SUPERSEDED preserved in place / ownership guard) | FR-002, FR-004, FR-007 |
| #5280 / `4.0.0rc8_retire_stale_mission_template_forks` (the shipped sibling repair) | FR-005, FR-008 |
| DIRECTIVE_044 (shipped migration bodies frozen, drift is audit-only) | FR-008, C-001 |
| #5450 (CUSTOMIZED move refuses an occupied destination) | FR-005 |
