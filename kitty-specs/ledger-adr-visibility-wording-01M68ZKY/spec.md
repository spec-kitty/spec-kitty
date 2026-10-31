# Mission Specification: Reconcile the migration-ledger ADR's visibility wording with the shipped read surface

**Mission Branch**: `ledger-adr-visibility-wording-01M68ZGC`
**Created**: 2026-10-31
**Status**: Draft
**Input**: User description: "spec-kitty/spec-kitty#6362 — Migration ledger: reconcile ADR visibility wording with shipped `migrate ledger` command. ADR `2026-10-17-1` §5 and its #E deliverable still name `doctor migrations` + `upgrade --list-applied`; the shipped read surface is `spec-kitty migrate ledger [--json]`. Documentation reconciliation only."

## Problem

The Accepted ADR `docs/adr/4.x/2026-10-17-1-explicit-migration-ledger.md` decides, in §5
("Visibility — one pending-source, two read surfaces"), that visibility is delivered by a new
doctor sub-surface `spec-kitty doctor migrations` plus an `upgrade --list-applied` flag, and its
#E deliverable repeats that spelling. Neither command exists. The ledger mission that implemented
the decision shipped one read surface instead — `spec-kitty migrate ledger`
(`src/specify_cli/cli/commands/migrate_cmd.py`), with `--json` emitting the same structured
report, consuming the single pending source `VersionDetector.applicable_migrations`.

The ADR already *knows* this: an incidental note added at closeout (~lines 391-395) records the
divergence. But the decision text a reader lands on first — §5 and the #E child list — still
promises commands that do not exist, so anyone following the ADR to inspect the ledger runs a
command that fails, and anyone re-planning #E would re-commission a surface that was deliberately
not built. The note is a comment about the decision; the decision must state what shipped.

Scope is documentation only. No new command aliases, no ledger implementation, no change to
migration semantics, no re-opening of the design.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The ADR's visibility decision names the command that exists (Priority: P1)

A maintainer reads §5 of the accepted ledger ADR to inspect what the ledger has applied, copied
the command the decision names, and runs it. The command works: it prints the declared, applied,
pending and drift state, partitioned tracked/clone-local, and `--json` gives the same data.
The historical proposal (`doctor migrations`, `upgrade --list-applied`) survives in the ADR as
explicitly marked history, so the decision trail is not rewritten.

**Why this priority**: A decision record whose "current visibility" section names a non-existent
command is a trap: it misdirects the reader and invites a future agent to build the wrong surface
(a second read path that would diverge from the ledger).

**Independent Test**: Read §5 and the #E bullet; grep every `spec-kitty <command>` snippet in
those sections against the live Typer walk; run each named command path against the built CLI.

**Acceptance Scenarios**:

1. **Given** the ADR's §5 visibility section, **When** a reader extracts its
   `spec-kitty …` command snippets, **Then** every extracted path resolves to a registered CLI
   command and `spec-kitty migrate ledger` is among them.
2. **Given** the #E deliverable bullet, **When** a reader follows it, **Then** it names
   `spec-kitty migrate ledger [--json]` and the single pending source, not the retired proposal.
3. **Given** the historical proposal, **When** a reader reaches the text that mentions
   `doctor migrations` / `upgrade --list-applied`, **Then** it is labelled as a rejected or
   historical proposal rather than as the current decision.

### User Story 2 - Partition, pending and drift wording agree with the shipped report (Priority: P2)

The ADR's descriptions of the tracked/clone-local partition, the single pending source, and
audit-only drift match what `spec-kitty migrate ledger` actually reports, so the ADR remains a
correct description of behaviour and not only of intent.

**Why this priority**: The issue's acceptance criteria require the reconciliation to cover these
descriptions; a command-name swap that leaves contradictory semantics behind would be worse than
the original wording.

**Independent Test**: Compare §5 (and the closeout notes that describe partition/pending/drift)
with `spawn`/`assemble_report`/`_ledger_step_state` in `migrate_cmd.py` and with
`tests/specify_cli/upgrade/test_migrate_ledger_cmd.py`.

**Acceptance Scenarios**:

1. **Given** §5's description of the two partitions and the pending source, **When** compared
   with the shipped command's report, **Then** no statement names a state or source the command
   does not emit.
2. **Given** the drift paragraph (§4/§5), **When** read against the shipped report, **Then** it
   still says drift is audit-only and read-only, never auto-reapplied.

### Edge Cases

- The closeout note at ~391-395 already says the shipped name differs; after the fix it must not
  read as a live divergence between two equally-current statements (it becomes a record of the
  decision to build one surface, still true).
- `doctor` remains a real command group with real sub-surfaces; the fix must not imply the group
  is broken, only that it has no `migrations` sub-surface.
- Other ADRs may legitimately reference proposals that never shipped; the guard added here is
  scoped to this ADR's current visibility decision, not to ADR prose in general.
- ADR frontmatter `updated:` date and the ADR inventory entries (`docs/adr/4.x/index.md`,
  `docs/development/page-inventory.yaml`, `docs/development/docs-retrieval-index.yaml`) must stay
  consistent with the edit.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Visibility decision names the shipped surface | As a maintainer reading §5, I want the visibility decision to name `spec-kitty migrate ledger [--json]` so that following the ADR runs a command that exists. | High | Open | [build] | no — the section currently names only commands that do not exist |
| FR-002 | #E deliverable names the shipped surface | As a maintainer re-planning the #E child, I want the deliverable to name `spec-kitty migrate ledger [--json]` so that a re-run does not re-commission a retired surface. | High | Open | [build] | no — #E currently names the retired proposal only |
| FR-003 | Historical proposal retained and marked historical | As a reader of the decision trail, I want the original `doctor migrations` / `upgrade --list-applied` proposal kept but labelled historical so that the record of why it changed survives. | Medium | Open | [build] | no — today the stale spelling is presented as the current decision |
| FR-004 | Partition, pending and audit-only drift wording agree with the command | As a maintainer, I want the ADR's partition/pending/drift descriptions to match what `migrate ledger` reports so that the ADR describes behaviour, not just intent. | Medium | Open | [build] | yes — no wording change needed where already accurate (verified, not assumed) |
| FR-005 | Guard against phantom commands in the current visibility decision | As a maintainer, I want a docs test that fails when the ADR's current visibility decision names an unregistered `spec-kitty` command path, so that the wording cannot drift back. | Medium | Open | [ratchet] | no — the guard fails on the pre-fix ADR |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Docs freshness gate is clean | `uv run python -m scripts.docs.check_docs_freshness --ci` reports `errors=0` for the touched pages, and the ADR inventory regenerators produce no diff after the edit. | Maintainability | High | Open |
| NFR-002 | Spelling and structural lint stay green | The docs spelling/structural checks that cover `docs/adr/**` pass on the edited page, with no new allowlist entries. | Maintainability | Medium | Open |
| NFR-003 | Diff stays inside the documentation surface | The change touches the ADR, its inventory entries if regeneration requires it, one docs test, and the changelog — nothing under `src/`. Measured by `git diff --stat` on the mission branch. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No command aliases | Do not implement `spec-kitty doctor migrations` or `upgrade --list-applied`, even as aliases; the ADR is what changes. | Technical | High | Open |
| C-002 | No ledger or migration-semantics change | `migrate_cmd.py`, the ledger modules and migration behaviour stay untouched. | Technical | High | Open |
| C-003 | Preserve decision history | The original proposal is not deleted from the ADR; it is marked historical with the reason it was not built. | Business | High | Open |

### Key Entities

- **ADR `2026-10-17-1`**: the accepted decision record; §5 (visibility) and the #E child bullet are the edited statements, the closeout note (~391-395) is the existing record of the divergence.
- **`spec-kitty migrate ledger [--json]`**: the shipped read-only visibility surface, single pending source `VersionDetector.applicable_migrations`.
- **Docs guard test**: a test under `tests/docs/` that binds the ADR's current visibility decision to the live Typer command surface.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero `spec-kitty` command paths referenced by §5 or #E of the ADR are unregistered in the live CLI surface; `spec-kitty migrate ledger` is referenced in both — [build] · no-op passable: no
- **SC-002**: The strings `doctor migrations` and `upgrade --list-applied` appear in the ADR only inside text that is explicitly marked historical — [build] · no-op passable: no
- **SC-003**: `check_docs_freshness --ci` and the ADR inventory regenerators report no error and no diff after the edit — [ratchet] · no-op passable: no
- **SC-004**: The mission diff contains no file under `src/` — [ratchet] · no-op passable: no
