# Mission Specification: Remote-only branch recovery remedy

**Mission Branch**: `kitty/mission-remote-only-branch-remedy-01M7X5Z5` (lands on `issue-5287-remote-only-coord-remedy`)
**Created**: 2026-11-20
**Status**: Draft
**Input**: #5287 (P3, parent #2720): a fresh clone whose coordination branch exists only on a remote gets a raw, remedy-less status refusal and recovery text that is false and incomplete.

## Intent Summary

- **Primary actor**: an operator (or an agent acting for one) working in a fresh clone, a CI checkout, or any checkout that has no local head for a Mission's coordination branch or Mission topic branch, while the branch exists on a remote.
- **Trigger**: any command that reads the Mission's status (`spec-kitty agent tasks status`, `next` query mode, `events`, the consolidation forecast) or that reports the coordination worktree as unmaterialized (`spec-kitty materialize`, `doctor coordination`, a coordination write refusal).
- **Desired outcome**: the command refuses with a typed, recognisable error whose text tells the operator, in order, the exact commands that unblock the read: fetch the branch from the remote that owns it (skipped when this clone already has the remote-tracking ref), create the local branch from it, then run the coordination doctor (or re-run the command).
- **Rule that must always hold**: the status read never silently reads a different source. A remote-only branch is a refusal, not a fallback to the remote-tracking ref, and never an empty history.
- **Canonical terms**: *remote-only branch* (a branch with no local head that a remote holds), *coordination branch*, *Mission topic branch*, *status read door*, *remedy*. The word "sync" is not used.
- **Confirmed by**: operator rulings of 2026-11-20 for #5287 (Decision Moment `01M7X5ZH6Q8WMSNFVTYHTRNERY`).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Status board on a fresh clone tells me how to recover (Priority: P1)

An operator clones a repository whose `lanes_with_coord` Mission has its coordination branch only on the remote, and asks for the status board. Today the command exits 1 with "ref does not resolve to a commit (missing)" and no next step.

**Why this priority**: it is the observed failure (R1) and blocks every status read on a fresh clone.

**Independent Test**: build a remote-only coordination Mission, run `agent tasks status --json`, and check the error code and remedy text.

**Acceptance Scenarios**:

1. **Given** a coordination Mission whose coordination branch has no local head but a remote holds it, **When** the operator runs `spec-kitty agent tasks status --mission <m> --json`, **Then** the command exits non-zero with error code `STATUS_SURFACE_REF_REMOTE_ONLY` and the message names the resolved remote, the `git branch <b> <remote>/<b>` step and the `spec-kitty doctor coordination --mission <m> --fix` step.
2. **Given** the same Mission after the operator runs the printed `git branch` step, **When** they run the status board again, **Then** it succeeds.

---

### User Story 2 - Recovery text is truthful and complete everywhere (Priority: P1)

The unmaterialized-coordination refusal today says the checkout "has not fetched" the branch (false on a fresh clone, which has fetched it), always names `origin`, and omits the `git branch` step. `doctor coordination` prints different, complete steps.

**Why this priority**: about twenty commands relay this one text, so a wrong text misleads everywhere (R3).

**Independent Test**: build the remote-only fixture whose only remote is not named `origin` and compare the exception text, the doctor finding and the write refusal.

**Acceptance Scenarios**:

1. **Given** a remote-only coordination branch whose only remote is `coord-remote`, **When** the unmaterialized-coordination refusal is built, **Then** its next step contains `coord-remote`, contains `git -C <root> branch <b> coord-remote/<b>`, contains the doctor `--fix` command, and does not contain "has not fetched" or `origin`.
2. **Given** the clone already has `refs/remotes/<remote>/<b>`, **When** the remedy is composed, **Then** it has no fetch step.
3. **Given** the same Mission, **When** `doctor coordination`, the unmaterialized refusal and the coordination write refusal each report it, **Then** all three carry the identical remedy steps.

---

### User Story 3 - A remote-only Mission topic branch gets the same refusal (Priority: P2)

A `topology_source: default` Mission reads its PRIMARY-partition status from its Mission topic branch when no checkout holds it. When that branch is remote-only, the read fails with the same raw error.

**Why this priority**: the same latent shape; smaller audience.

**Independent Test**: build a default-topology Mission whose topic branch is remote-only and read its status through the door.

**Acceptance Scenarios**:

1. **Given** a default-topology Mission whose topic branch has no local head and a remote holds it, **When** its status is read, **Then** the read refuses with `STATUS_SURFACE_REF_REMOTE_ONLY` and a remedy whose last step is to re-run the command (not the coordination doctor).

### Edge Cases

- Several remotes, none named `origin` and none configured for the branch: the remedy names `<remote>` as a placeholder and lists the configured remotes, rather than guessing.
- The resolved remote has no tracking ref but exactly one other remote does: the remedy uses that remote and skips the fetch.
- A ref that exists locally but names a missing object (corruption) keeps raising `STATUS_SURFACE_REF_UNREADABLE`, never the remote-only error.
- A coordination branch deleted everywhere keeps raising `COORDINATION_BRANCH_DELETED`.
- The write path (`for_write`) is unchanged: remote-only coordination writes keep their existing refusal code, now with the shared remedy text.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | One canonical remote-only remedy | As an operator, I want one remedy text for a remote-only branch, composed in one place, so that every command tells me the same truthful steps. | High | Open | [build] | no |
| FR-002 | Resolved remote, never hard-coded | As an operator with a remote not named `origin`, I want the remedy to name the remote that owns the branch so that the commands I copy work. | High | Open | [build] | no — the fixture's only remote is `coord-remote` |
| FR-003 | Fetch step only when needed | As an operator whose clone already has the remote-tracking ref, I want the remedy to skip the fetch step so that it lists only what is needed. | Medium | Open | [build] | no — paired with the no-tracking-ref variant on the same fixture |
| FR-004 | No false "has not fetched" claim | As an operator on a fresh clone, I want the unmaterialized-coordination refusal to stop claiming the branch was not fetched so that I am not misled. | High | Open | [build] | no |
| FR-005 | Doctor, refusal and write refusal share the remedy | As an operator, I want `doctor coordination`, the unmaterialized refusal and the coordination write refusal to embed the identical remedy so that they never drift. | High | Open | [build] | no |
| FR-006 | Typed remote-only refusal at the status read door (coordination branch) | As an operator, I want a status read of a remote-only coordination branch to refuse with a typed remote-only error carrying the remedy, instead of a raw unreadable-ref error. | High | Open | [build] | no |
| FR-007 | Typed remote-only refusal for a Mission topic branch | As an operator, I want the same refusal when the status read source is a remote-only Mission topic branch. | Medium | Open | [build] | no |
| FR-008 | Existing handlers keep working | As a maintainer, I want every caller that already handles the unreadable-ref error to handle the remote-only error unchanged, so that no command regresses into a traceback. | High | Open | [build] | no — `next` query mode must report the new code |
| FR-009 | Status board relays the refusal | As an operator, I want `spec-kitty agent tasks status` to show the remote-only code and remedy. | High | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No extra cost on a healthy read | A status read whose ref resolves spawns no more git subprocesses than before (0 added on the success path). | Performance | High | Open |
| NFR-002 | No network contact | Composing the remedy and classifying a remote-only branch contact no remote (0 `ls-remote`/`fetch` calls added). | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No remote-tracking read source | The status read door must not read a remote-tracking ref (operator ruling 1; any such source belongs to #7408 under an ADR amendment). | Technical | High | Open |
| C-002 | #5936 stays separate | Write-side materialisation from the remote-tracking ref is out of scope. | Business | High | Open |
| C-003 | #7449 stays with #7408 | The backfill migration's settling on an unreadable ref and `MigrationResult` are unchanged. | Business | High | Open |
| C-004 | Layer direction | The remedy builder lives where both `mission_runtime` and `specify_cli` can import it without growing the `mission_runtime → specify_cli` ledger. | Technical | High | Open |
| C-005 | Destination-branch remedy untouched | The policy pre-flight's missing-destination remedy (#7726) keeps its wording unless it can share the builder cleanly. | Technical | Medium | Open |

### Key Entities

- **Remote-only branch facts**: the branch name, the remote judged to own it (or none when ambiguous), whether this clone already holds the remote-tracking ref, and the configured remotes.
- **Remote-only status refusal**: a typed error, a kind of unreadable-ref error, with its own stable code and the remedy text.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the remote-only fixture, 100% of the three remedy-emitting surfaces (doctor finding, unmaterialized refusal, write refusal) carry the identical remedy text — [build] · no-op passable: no
- **SC-002**: On the remote-only fixture, the status board exits non-zero with the remote-only code, and after the operator runs the printed local-branch step, the same command succeeds — [build] · no-op passable: no
- **SC-003**: 0 occurrences of the phrase "has not fetched" and 0 hard-coded `origin` in remote-only remedy texts — [build] · no-op passable: no

## Assumptions

- The coordination probe's existing verdict that a branch is present (local, remote-tracking, or reported by the remote) is trusted; when a local head is absent the branch is treated as remote-only. If the branch is in fact gone, the printed fetch step fails loudly, which is acceptable.
- The coordination topology state model is not extended with a new member; the remote-only split is decided at the single failure point (design choice recorded in the Phase-2 debrief).
