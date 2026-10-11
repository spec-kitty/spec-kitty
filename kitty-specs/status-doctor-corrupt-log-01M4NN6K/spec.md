# Mission Specification: Status Doctor Corrupt Log

**Mission Branch**: `issue-5924-status-doctor-corrupt-log`  
**Created**: 2026-10-11  
**Status**: Approved intent; ready for planning  
**Input**: User approved “start work. only open a pr do not merge. make sure to review thoroughly” for the presented #5924 bounded fix.  
**Audience**: software-engineer operating a Mission, with automation-agent consuming diagnostics.

## Intent Summary

An operator runs `spec-kitty agent status doctor` when a Mission's authoritative `status.events.jsonl` is corrupt or unreadable. The result must be an actionable ERROR, never a false healthy result or an unhandled traceback, whether `status.json` exists or not. All log and snapshot evidence must remain unchanged. Only #5924 is addressed; see #5304 for context only. This small-defect scenario and issue branch were confirmed before start; no further discovery or unresolved product decision remains.

Current, planning/base and mission target branch are all `issue-5924-status-doctor-corrupt-log` (resolver match true), with explicit `single_branch` topology. Final GitHub PR targets `main`. Do not merge/consolidate or push main.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Diagnose Unreadable Authority (Priority: P1)

As a Mission operator, I need doctor to explain when status history cannot be trusted, so I do not continue work based on a misleading snapshot or empty fallback.

**Why this priority**: Both reported paths defeat diagnosis: no snapshot can falsely pass; an existing snapshot can trigger a crash.

**Independent Test**: Diagnose each corruption/read-failure fixture, once without a snapshot and once with a valid snapshot. In each case observe ERROR, not healthy, file/reason and safe next action, with no unhandled exception.

**Acceptance Scenarios**:

1. **Given** invalid JSON in a log with no snapshot, **When** doctor runs, **Then** an ERROR names the log and parse reason and the Mission is not healthy.
2. **Given** the same log and a valid snapshot, **When** doctor runs, **Then** it returns the same class of ERROR instead of crashing during drift checks.
3. **Given** a non-object row, schema-invalid event, invalid UTF-8, or file read failure, **When** doctor runs with either snapshot state, **Then** it reports the actual failure rather than treating history as empty.
4. **Given** blank physical lines before a malformed record, **When** its record location is available, **Then** the diagnostic uses the correct physical 1-based record line; whole-file I/O failures have no invented line.
5. **Given** the unhealthy Mission, **When** the operator uses text or JSON output, **Then** the ERROR is visible, the command exits 1, JSON exposes `healthy: false`, and neither output contains a traceback.

### User Story 2 - Preserve Evidence and Healthy Checks (Priority: P2)

As an operator, I need safe recovery guidance and unchanged evidence, while keeping useful diagnosis for intact Missions.

**Why this priority**: A corruption report must not cause further history loss or disable legitimate health checks.

**Independent Test**: Compare exact log/snapshot bytes and missing-file state before/after each invocation; repair only the test fixture and confirm valid history is accepted through the same entry point. Re-run existing drift/reconciliation controls.

**Acceptance Scenarios**:

1. **Given** unreadable history, **When** doctor reports it, **Then** it recommends preserving evidence and restoring trusted history or correcting access, then rerunning; it does not recommend blind deletion, automatic repair, or backfill/materialize-only recovery.
2. **Given** any failure fixture, **When** doctor runs, **Then** all existing log/snapshot bytes and absent-file states are unchanged.
3. **Given** valid mixed lifecycle, status and annotation records including blank lines, **When** doctor runs with either snapshot state, **Then** it accepts that history and retains normal health-check behavior.
4. **Given** missing, empty or blank-only history, **When** doctor runs, **Then** existing missing/empty behavior is preserved rather than reported as malformed history.
5. **Given** intact history with real snapshot drift or WP prompt/event mismatch, **When** doctor runs, **Then** existing drift and reconciliation findings remain available.

### Edge Cases

- Malformation after valid records and blank rows; distinguish JSONL record line from an inner JSON error location.
- All corruption classes with snapshot absent/present; a snapshot never proves log readability.
- Decode failures may have no truthful line exposed by the reader; report a line only if accurately available.
- Permission/read failures must be deterministic in tests under elevated privileges, not dependent on chmod behavior.
- Log-derived checks, including reviewer self-approval reading the same history, cannot run on unreadable authority or turn it into empty-membership/backfill advice; independent checks still run.
- An otherwise valid annotation envelope with malformed delta or subtasks must be diagnosed as corrupt history, not escape as a decoder AttributeError.
- Existing warnings make a Mission not healthy under existing semantics; positive controls require an otherwise intact fixture.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Failure is always an ERROR | As an operator, I want corrupt/unreadable history to yield an ERROR and an unhealthy result without unhandled read/parse exceptions, regardless of snapshot presence. | High | Open | [build] | no |
| FR-002 | Truthful location and reason | As an operator, I want the resolved log path, failure reason and physical 1-based record line when available; no line is fabricated for whole-file I/O. | High | Open | [build] | no |
| FR-003 | Visible CLI failure | As an operator or automation consumer, I want text and JSON diagnostics to expose the ERROR, exit 1, JSON healthy false, and no traceback. | High | Open | [build] | no |
| FR-004 | Evidence-safe recovery | As an operator, I want evidence-preservation and trusted-history/access recovery guidance, then rerun, without deletion, auto-repair or misleading empty-history guidance. | High | Open | [build] | no |
| FR-005 | Preserve stored evidence | As an operator, I want doctor to leave every log/snapshot byte and absent-file state unchanged. | High | Open | [ratchet] | yes — pair failure fixtures with repaired-history controls proving the same probe reads real history |
| FR-006 | Preserve legitimate checks | As an operator, I want accepted mixed event families, blank/missing/empty history behavior and existing drift/WP reconciliation checks unchanged. | High | Open | [ratchet] | yes — paired with FR-001 malformed variants on the same fixtures and explicit drift/mismatch controls |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Complete bounded failure matrix | All five failure classes are verified in both snapshot states (at least ten negative combinations) and both CLI output modes are verified. | Reliability | High | Open |
| NFR-002 | Zero mutation | Zero changed log/snapshot bytes or newly created missing log/snapshot files across all acceptance cases. | Integrity | High | Open |
| NFR-003 | Proportionate verification | Every changed branch has targeted tests; new-code coverage is at least 90%; targeted lint/type/format checks have zero newly introduced errors. No full heavy local suite. | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|--------|--------|
| C-001 | Bounded status-doctor ownership | Address #5924 only. Decision doctor (see #5304), automatic repairs, general reducer changes and new shared cross-doctor abstractions are outside scope. | Scope | High | Open |
| C-002 | Canonical authority | Retain existing store reader as event acceptance authority; no separate doctor parser. Only a minimal annotation-decoder AttributeError normalization into canonical line-bearing StoreError is approved; no model/parser refactor. | Technical | High | Open |
| C-003 | PR-only delivery | Work stays on the dedicated issue branch, one bounded WP; independent thorough review and a PR to main, never merge/consolidate or main push. | Workflow | High | Open |
| C-004 | Failing-first contract | Commit a failing-first acceptance regression test before any production fix; transitional regression markers must be removed once fixed. | Quality | High | Open |

### Key Entities *(include if the mission involves data)*

- **Mission**: the unit whose status is diagnosed.
- **Status event log**: append-only authoritative history; existing supported record families remain authoritative.
- **Status snapshot**: derived view, present or absent; not proof that the log is readable.
- **Finding**: operator-visible severity, diagnostic and recommended action; an ERROR indicates unreadable authority.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of the five failure classes across both snapshot states, the operator receives an actionable error rather than false health or a crash. — [build] · no-op passable: no
- **SC-002**: Both output modes communicate failure and return exit 1 in all exercised failure cases; automation sees healthy false. — [build] · no-op passable: no
- **SC-003**: Every diagnostic identifies the affected file and reason; all available record lines are accurate and no whole-file I/O line is invented. — [build] · no-op passable: no
- **SC-004**: All evidence remains byte-identical, and all intact-history, missing/empty, drift and reconciliation controls retain expected outcomes. — [ratchet] · no-op passable: yes — paired with SC-001 corrupt variants and repaired-history controls

## Assumptions and Dependencies

No external-package/schema, version, deployment or product architecture change is required. Prior live investigation is recorded in [research.md](research.md), not claimed as new execution. Issue owner is Ivan-Melck. Independent review is required before PR handoff. Implementation must resolve only local diagnostic details without widening this approved scope.
