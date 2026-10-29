# Mission Specification: Owned-checkout issue-verdict cleanup

**Mission Branch**: `issue-6354-owned-issue-verdict-cleanup`
**Created**: 2026-10-27
**Status**: Draft
**Input**: User description: "Owned-checkout issue-verdict cleanup: (#6354) the legacy issue-matrix.md migration must be owned-checkout aware so an owned mission's migrated issue-matrix.json lands in its owned checkout; (#6353) every owned-checkout refusal emits one shared JSON shape -- strict C2 `{ok:false, error:{code,message}}` -- across all commands (helper callers plus mission create, move-task catch-all, mark-status, decision verbs), with orchestrator-api contract bump 1.18.0 -> 1.19.0."

## Intent Summary (confirmed 2026-10-27)

The primary actor is an agent or orchestrator that runs a Spec Kitty command against an
owned checkout (explicit `--owned-checkout`, or flagless from inside one) and reads the
command's `--json` output.

1. **Migration placement (#6354).** When an owned Mission still holds a legacy
   `issue-matrix.md` and an issue verdict is recorded, the migrated structured issue matrix
   is written into the owned checkout, never against the repository root checkout. The
   verdict is recorded and the command succeeds. Today the command fails with exit 1.
2. **One refusal shape (#6353).** Every owned-checkout refusal in `--json` mode prints the
   adopted CLI error contract (C2) on stdout and exits 1:
   `{"ok": false, "error": {"code": <registered owned code>, "message": <text>}}`. There is
   no top-level `error_code` key. Command-specific facts the refusal must still carry
   travel in one optional top-level `context` object. A command that stamps its payloads
   with `spec_kitty_version` keeps that stamp as a top-level key.

Rules that always hold: an owned refusal writes nothing; `error.code` is a
registered owned refusal code on every shared-renderer path (the move-task owned catch-all
and the mark-status in-command owned failure keep their existing code posture); human-mode refusal text (`Error: [CODE] message` on stderr,
exit 1) is unchanged; every command's non-owned errors keep their current shape.

Operator rulings are recorded as Decision Moments (`spec-kitty agent decision verify`
reports clean): refusal shape = C2; strict C2 (no top-level `error_code`); every owned
refusal in scope, including the four that bypass the shared renderer; decision verbs'
owned refusal on stdout; extras under `context`; `spec_kitty_version` stays top-level;
human mode unchanged.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Recording a verdict on an owned Mission with a legacy matrix (Priority: P1)

An agent records an issue verdict for an owned Mission whose owned checkout still holds a
legacy `issue-matrix.md`. The legacy rows are migrated into the structured matrix inside
the owned checkout, the new verdict is added beside them, and the repository root
checkout is left untouched.

**Why this priority**: it is a crash on a write path for owned Missions that are meant to
reach 4.0.0 GA with no known gaps in owned-checkout propagation (operator triage of
#6354).

**Independent Test**: create an owned-only Mission, place a legacy `issue-matrix.md` in
the owned checkout, run `agent issue-verdict --owned-checkout <P> --json`, and check the
exit code, the owned checkout's structured matrix, and the repository root checkout.

**Acceptance Scenarios**:

1. **Given** an owned-only Mission whose owned checkout holds a legacy `issue-matrix.md`
   with one row, **When** a verdict for a second issue is recorded with
   `--owned-checkout`, **Then** the command exits 0 and the owned checkout's structured
   matrix holds both rows.
2. **Given** the same fixture, **When** the verdict is recorded, **Then** the repository
   root checkout holds no copy of the Mission and no structured matrix.
3. **Given** the same fixture run flagless from inside the owned checkout, **When** the
   verdict is recorded, **Then** the outcome matches scenario 1.
4. **Given** a non-owned Mission with a legacy `issue-matrix.md` in the repository root
   checkout, **When** a verdict is recorded, **Then** the migration behaves exactly as
   before (positive control on the non-owned path).

---

### User Story 2 - Parsing an owned-checkout refusal from any command (Priority: P1)

An agent drives several commands with `--owned-checkout`. When a command refuses (for
example, the owned checkout resolves no Mission, is the repository root checkout, or the
topology is not supported), the agent parses `ok`, `error.code` and `error.message` the
same way for every command. It never has to know which command spoke.

**Why this priority**: today an owned refusal carries one of six different key sets
depending on the command; issue-verdict's refusal does not even carry the key its own
errors use (`code`), so a consumer misses the identifier.

**Independent Test**: for each in-scope command, trigger one owned refusal in `--json`
mode and assert the payload is exactly the C2 core plus any declared `context` /
`spec_kitty_version` keys, on stdout, exit 1.

**Acceptance Scenarios**:

1. **Given** an owned checkout that resolves no Mission, **When** `agent issue-verdict
   --owned-checkout <P> --json` runs, **Then** stdout is
   `{"ok": false, "error": {"code": "MISSION_CONTEXT_UNRESOLVED", "message": ...}}` and
   the exit code is 1.
2. **Given** any in-scope command and an owned refusal, **When** it runs with `--json`,
   **Then** the top-level keys are a subset of `{ok, error, context, spec_kitty_version}`,
   `ok` is `false`, `error` has exactly `code` and `message`, and there is no top-level
   `error_code`.
3. **Given** `agent tasks mark-status` refusing an owned checkout, **When** it runs with
   `--json`, **Then** the facts that tell the agent nothing was applied
   (`state_applied: false`, empty `event_ids`, and the rest of today's result keys) are
   present under `context`.
4. **Given** an `agent decision` verb refusing an owned checkout with `--json`, **When**
   it runs, **Then** the C2 refusal is on stdout (its other errors stay where they are
   today).
5. **Given** any in-scope command without `--json`, **When** it refuses an owned
   checkout, **Then** stderr shows `Error: [<CODE>] <message>` exactly as before.
6. **Given** any in-scope command and a valid owned checkout, **When** it succeeds,
   **Then** its success payload is byte-identical to today's (positive control).

---

### User Story 3 - Orchestrator callers keep classifying host refusals (Priority: P2)

An external orchestrator calls `orchestrator-api check-prerequisites` and
`orchestrator-api next`. Both delegate to host commands whose owned refusal now has the
C2 shape. The orchestrator still receives the real error code (with the existing
`MISSION_CONTEXT_UNRESOLVED` → `MISSION_NOT_FOUND` translation) and a readable message,
and the contract version tells it that the embedded host payload changed.

**Why this priority**: the orchestrator-api is a versioned public contract; changing what
it embeds without a version bump would break consumers silently.

**Independent Test**: drive the orchestrator verb so the host delegate emits an owned
refusal and assert the orchestrator envelope's `error_code`, message and
`contract_version`.

**Acceptance Scenarios**:

1. **Given** a host check-prerequisites owned refusal, **When** `orchestrator-api
   check-prerequisites` classifies it, **Then** the envelope's `error_code` is the host
   code (translated when it is `MISSION_CONTEXT_UNRESOLVED`) and the message is the host
   `error.message` text, not a serialized object.
2. **Given** any orchestrator-api call, **When** it returns, **Then** `contract_version`
   is `1.19.0` and the orchestrator-api reference documents the change.

### Edge Cases

- An owned refusal raised with an unregistered code is still a programming error, never a
  rendered refusal (existing fail-closed behaviour is kept).
- A legacy `issue-matrix.md` that is malformed in an owned checkout still fails loudly as
  `malformed_legacy_matrix`; nothing is written to either checkout.
- An owned Mission whose structured matrix already exists in the owned checkout is not
  re-migrated from a stale legacy file.
- A refusal raised before the command knows whether `--json` was requested (commands
  with no `--json` option: `agent action implement/review`, `research`) keeps its human
  rendering only.
- `invocations list` has no non-owned error payload today; its owned refusal adopts C2
  like the rest.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Owned legacy migration lands in the owned checkout | As an agent, I want the legacy issue-matrix migration of an owned Mission to write its structured matrix into the owned checkout so that recording a verdict succeeds and never touches the repository root checkout. | High | Open | [build] | no -- the command exits 1 today on this fixture |
| FR-002 | Owned legacy migration preserves the legacy rows | As an agent, I want the migrated matrix to keep every legacy row beside the new verdict so that no recorded verdict is lost. | High | Open | [build] | no -- paired with FR-001 on the same fixture |
| FR-003 | Non-owned legacy migration unchanged | As an agent on a non-owned Mission, I want the legacy migration to behave exactly as today so that nothing regresses. | Medium | Open | [ratchet] | yes -- paired with FR-001 as its same-fixture positive control |
| FR-004 | One C2 owned refusal for every shared-renderer caller | As an agent, I want every command whose owned refusal goes through the shared renderer to print `{ok:false, error:{code,message}}` on stdout and exit 1 so that I parse refusals one way. | High | Open | [build] | no -- issue-verdict prints a different shape today |
| FR-005 | No top-level `error_code` on owned refusals | As an agent, I want owned refusals to carry the code only in `error.code` so that there is one place to read it. | High | Open | [build] | no -- the renderer adds `error_code` today |
| FR-006 | Owned refusals outside the shared renderer adopt C2 | As an agent, I want `agent mission create`, the move-task owned catch-all, the mark-status owned failure and the `agent decision` verbs to emit the same C2 refusal so that no owned refusal is the odd one out. | High | Open | [build] | no -- each emits a different shape today |
| FR-007 | Command-specific refusal facts under `context` | As an agent, I want a refusal's command-specific facts (for example mark-status's nothing-applied facts, spec-commit's `committed: false`, setup-plan's `phase_complete: false`) in one optional `context` object so that the C2 core stays strict. | High | Open | [build] | no -- these keys are top-level today |
| FR-008 | `spec_kitty_version` stamp stays top-level | As an agent, I want commands that stamp every payload with `spec_kitty_version` to keep that stamp top-level on owned refusals, and the commands that drop it today to add it, so that the stamp is uniform per command. | Medium | Open | [build] | no -- setup-plan and record-analysis drop it today |
| FR-009 | Decision verbs' owned refusal on stdout | As an agent, I want an `agent decision` verb's owned refusal in `--json` mode on stdout so that it matches every other owned refusal. | Medium | Open | [build] | no -- it is on stderr today |
| FR-010 | Human-mode owned refusal unchanged | As an operator, I want the non-JSON owned refusal to stay `Error: [CODE] message` on stderr with exit 1 so that terminal output does not change. | Medium | Open | [ratchet] | yes -- paired with FR-004 on the same refusal fixture |
| FR-011 | Success and non-owned error payloads unchanged | As an agent, I want every in-scope command's success payload and non-owned error payloads unchanged so that only owned refusals move. | High | Open | [ratchet] | yes -- paired with FR-004/FR-006 on the same command fixtures |
| FR-012 | Orchestrator-api classifies the new host shape | As an orchestrator, I want `orchestrator-api check-prerequisites` and `orchestrator-api next` to read the host's C2 owned refusal so that I keep getting the real code and a readable message. | High | Open | [build] | no -- the classifier reads top-level `error`/`error_code` today |
| FR-013 | Orchestrator-api contract version bump | As an orchestrator, I want `contract_version` raised to 1.19.0 and the change documented so that I can detect the embedded payload change. | High | Open | [build] | no -- version is 1.18.0 today |
| FR-014 | Decision recorded and earlier contract amended | As a maintainer, I want an ADR that records the shared owned refusal shape and amends the owned-checkout contract line "keeps each command's existing JSON envelope keys" so that the rule has one authority. | Medium | Open | [build] | no -- no such ADR exists |
| FR-015 | Shape pinned for every owned refusal path | As a maintainer, I want a test that drives an owned refusal through every in-scope command and asserts the exact shape so that a new or changed path cannot drift. | High | Open | [build] | no -- red until every path complies |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Diff coverage | New and changed lines reach at least 90% line coverage (the repository's diff-cover gate). | Maintainability | High | Open |
| NFR-002 | Static checks clean | Touched files pass `ruff check`, `ruff format --check --force-exclude` and `mypy` with zero findings and no new suppressions. | Maintainability | High | Open |
| NFR-003 | Complexity ceiling | No touched function exceeds cyclomatic complexity 15. | Maintainability | High | Open |
| NFR-004 | No write on refusal | 0 files created or modified in either checkout by any owned refusal exercised in the tests. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Registered codes only | `error.code` on an owned refusal rendered by the shared renderer is always a registered owned refusal code, and the existing fail-closed check on unregistered codes stays. The move-task owned catch-all and the mark-status in-command owned failure keep their existing code posture (any `ActionContextError` code; `MARK_STATUS_FAILED` fallback). | Technical | High | Open |
| C-002 | One owned-checkout authority | Ownership validation stays in the single shared owned-checkout surface; no command re-derives it (the single-authority architectural gate stays green with an empty allowlist). | Technical | High | Open |
| C-003 | Keep the terminality gate green | The issue-matrix terminality gate (ADR 2026-10-26-1, every issue-matrix row judged) is unaffected and its tests stay green. | Technical | High | Open |
| C-004 | Compatible with in-flight accept refusals | Accept's owned refusal adopts C2 here; new accept refusals in flight (see #6715) are not owned refusals and keep their own shape. | Business | Medium | Open |
| C-005 | No hosted surface | No hosted or sync surface is added or extended. | Technical | High | Open |
| C-006 | Tidy-first | Behaviour-preserving preparatory refactors land as separate, earlier commits than the behaviour change. | Technical | Medium | Open |

### Key Entities

- **Owned refusal**: a command's refusal to act on an owned checkout (invalid claim,
  repository root, unsupported topology, unresolvable Mission). Identified by its
  error code (a registered owned refusal code on every shared-renderer path).
- **C2 error envelope**: the adopted CLI error contract `{ok:false, error:{code,message}}`.
- **Refusal context**: the optional `context` object carrying command-specific facts on an
  owned refusal.
- **Legacy issue matrix**: an `issue-matrix.md` that predates the structured
  `issue-matrix.json`; it is migrated on the first structured write.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Recording a verdict on an owned Mission that holds a legacy matrix succeeds in 100% of the tested cases (explicit flag and flagless), with 0 files written to the repository root checkout. — [build] · no-op passable: no
- **SC-002**: 100% of the in-scope commands emit the same owned refusal shape in `--json` mode, and 0 of them emit a top-level `error_code` on an owned refusal. — [build] · no-op passable: no
- **SC-003**: An orchestrator receives the real host error code and a plain-text message for 100% of the tested host owned refusals, and every response reports contract version 1.19.0. — [build] · no-op passable: no
- **SC-004**: 0 changes to any in-scope command's success payload or non-owned error payload in the tested fixtures. — [ratchet] · no-op passable: yes -- paired with SC-002 on the same command fixtures

## Assumptions

- "In-scope commands" are the 23 callers of the shared owned-checkout renderer inventoried
  in `research.md`, plus `agent mission create`, the move-task owned catch-all, the
  mark-status owned failure and the `agent decision` verbs.
- Commands without a `--json` option keep only their human-mode refusal (no JSON shape to
  change).
- Tests that pinned the old owned refusal shapes are stale under this ruling and are
  re-pinned to the C2 shape (judged, not deleted).

## Dependencies

- Parent epics (context only): see #1878 (placement strangler, parent of the migration
  fix) and see #1801 (CLI user experience, parent of the refusal-shape fix).
- Related in-flight work (context only): see #6715 (accept/consolidate refusals) and
  see #4664 (decision verbs' stderr JSON, deferred).
