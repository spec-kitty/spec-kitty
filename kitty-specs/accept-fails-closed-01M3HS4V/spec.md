# Mission Specification: Accept fails closed on a stale or pending acceptance matrix

**Mission Branch**: `claude/project-thread-zj01ct`
**Created**: 2026-09-27
**Status**: Draft
**Input**: Operator instruction (Stijn, 2026-09-27): run the proposed milestone-11 slice "accept fails closed" (#4974, #4887, #4934; #4891 found already fixed on main and closed) through a governed mission. Brief-intake from the four GitHub issues and sub-epic #5227; discovery minimized by explicit operator instruction ("proceed").

## Intent Summary (confirmed by operator instruction)

- **Primary actors:** an operator running `spec-kitty accept`, an external orchestrator calling `spec-kitty orchestrator-api accept-mission`, and a concurrent agent recording `spec-kitty agent mission acceptance-verdict`.
- **Trigger:** a mission is accepted while its acceptance matrix is pending or failing, or while another agent records a failing verdict in the same window.
- **Desired outcome:** acceptance is recorded only when the canonical acceptance-matrix verdict, read fresh, passes. A committed failing verdict is never erased.
- **Invariant:** every read-modify-write of `acceptance-matrix.json` happens inside the mission's status lock through one shared write seam. Accept and orchestrator-api accept apply one readiness verdict.
- **Boundary:** matrix authoring gaps (#4162, #4232, #5025), `--no-commit` side effects (#4089) and issue-matrix non-verdict writers are out of scope (see Constraints).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A concurrent failing verdict survives accept (Priority: P1)

An operator runs `spec-kitty accept` on a mission with a pending negative invariant. The invariant's verification command takes a while. Meanwhile a second agent records a failing verdict (a new still-present negative invariant or a criterion `fail`), and it commits. Accept must not write its pre-check snapshot over that verdict. It must judge the fresh matrix and refuse.

**Why this priority**: This is the P0 (#4974). Today accept exits 0, stamps `accepted_at` and its commit flips `overall_verdict` from `fail` back to `pass`.

**Independent Test**: Run the `accept` CLI with the negative-invariant runner wrapped so the real `acceptance-verdict` command records a verdict mid-check, then assert on disk, in HEAD (`git show HEAD:<matrix>`) and on the exit code and `meta.json`.

**Acceptance Scenarios**:

1. **Given** FR-001=pass and a pending NI-SLOW, **When** `acceptance-verdict --negative-invariant NI-FAIL` (still present) commits while accept runs NI-SLOW's check, **Then** NI-FAIL survives in the written matrix, `overall_verdict` is `fail`, accept exits non-zero and `meta.json` has no `accepted_at`.
2. **Given** the same fixture, **When** `acceptance-verdict --criterion FR-001 --result fail` commits mid-check, **Then** FR-001 stays `fail` and accept refuses.
3. **Given** no concurrent verdict (positive control on the same fixture), **When** NI-SLOW passes, **Then** accept records NI-SLOW's result and accepts.

---

### User Story 2 - One locked write seam for the acceptance matrix (Priority: P1)

A contributor adding a new acceptance-matrix writer cannot bypass the status lock. Every writer goes through one seam that takes the lock, re-reads, splices and writes.

**Why this priority**: #4887 is the root cause of #4974. Fixing only the accept call site leaves the next writer to reopen the class.

**Independent Test**: A call-site gate fails when production code outside the seam calls the raw matrix writer. The seam's lock-spy test proves re-read and write happen inside the lock, and slow checks happen before it.

**Acceptance Scenarios**:

1. **Given** production code under `src/`, **When** the call-site gate scans it, **Then** only the seam (plus a named, shrink-only per-function allowlist) calls either unlocked writer, including attribute-style and aliased calls.
2. **Given** the seam, **When** the status lock cannot be acquired within the bounded timeout, **Then** no write happens and a lock-timeout error reaches the caller.

---

### User Story 3 - orchestrator-api accept-mission applies the host readiness verdict (Priority: P1)

An external orchestrator calls `accept-mission` on a mission whose acceptance matrix is pending (or whose `lanes.json` is missing). It must get `MISSION_NOT_READY` with the outstanding findings, and nothing is recorded.

**Why this priority**: #4934. Today `accept-mission` records `accepted_at` on a mission host `accept` refuses, and it bypasses the #4891 fix.

**Independent Test**: Run `orchestrator-api accept-mission` through the CLI on a mission with all WPs approved and a pending matrix; assert the envelope and `meta.json`.

**Acceptance Scenarios**:

1. **Given** all WPs approved and a pending matrix, **When** `accept-mission` runs, **Then** it exits non-zero with `MISSION_NOT_READY`, the envelope data names the failing checks, `meta.json` gains no `accepted_at`, `acceptance_mode` or `acceptance_history`, and HEAD is unchanged (the matrix may be updated in the working tree).
2. **Given** a mission without `lanes.json`, **When** `accept-mission` runs, **Then** it fails the same way with a blocked `lanes_manifest` check.
3. **Given** a genuinely acceptable mission (positive control), **When** `accept-mission` runs, **Then** it succeeds and records acceptance as before.

### Edge Cases

- The matrix vanishes between the pre-check read and the locked re-read: the seam starts from an empty, schema-valid matrix and still splices accept's owned rows (existing #4858 behavior).
- A row accept filled is already non-pending in the fresh matrix: the fresh value wins (NI-2 terminal immutability).
- A row exists only in the fresh matrix (added concurrently): it is kept.
- A row exists only in accept's snapshot (removed concurrently): it is not re-added.
- A negative invariant is re-registered concurrently (`acceptance-verdict --negative-invariant` resets it to `pending` with a new command, method or scope): accept's result, judged against the old definition, is discarded and the fresh `pending` row stays, so accept refuses.
- A failing verdict commits after the gate's splice but before `accepted_at` is written: the locked pre-stamp re-check sees it and acceptance is refused (FR-010).
- Diagnose mode (`mutate_matrix=False`) writes nothing and needs no lock.
- Lock timeout during accept: accept fails closed (non-zero, no write, no `accepted_at`).

## Requirements *(mandatory)*

### Row ownership rule (FR-003)

Accept contributes its value for row R to the fresh matrix only when **all** of these hold; otherwise the fresh row wins:

1. R was `pending` in accept's pre-check snapshot;
2. accept's value for R is no longer `pending` (accept judged it);
3. R is still `pending` in the fresh matrix;
4. R's judgement-defining fields are unchanged between snapshot and fresh matrix (negative invariant: `verification_method`, `verification_command`, `scope`; criterion: `proof_type`, `description`).

Rows present only in the fresh matrix are kept; rows present only in the snapshot are not re-added.

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Shared locked matrix write seam | As a contributor, I want one acceptance-matrix read-modify-write seam in `acceptance/matrix.py` that takes the mission status lock, re-reads the matrix, applies a caller splice and writes (committing only when asked), so that no writer can erase a concurrently committed row. | High | Open | [build] | no |
| FR-002 | Verdict command routes through the seam | As an agent recording a verdict, I want `acceptance-verdict` (criterion and negative-invariant modes) to use the shared seam instead of its private copy, so that there is one locked write path. | High | Open | [ratchet] | yes — positive control: patching the shared seam to raise makes the `acceptance-verdict` CLI fail, proving the wiring; the #4858 concurrency tests stay green |
| FR-003 | Accept splices only rows it owns | As an operator, I want the accept gate to run review-evidence population and negative-invariant checks outside the lock and then, through the seam in non-committing mode, splice only the rows it owns under the row ownership rule, so that a concurrently committed verdict survives (#4974). | High | Open | [build] | no |
| FR-004 | Accept judges the fresh matrix | As an operator, I want accept's evidence validation and `overall_verdict` judgement to use the fresh spliced matrix, so that a committed failing verdict blocks acceptance. | High | Open | [build] | no |
| FR-005 | Accept fails closed on lock timeout | As an operator, I want a status-lock timeout during the accept gate to block acceptance with a diagnostic and no matrix write, so that contention never degrades to an unlocked write. | High | Open | [build] | no — positive control: same fixture with no other lock holder accepts |
| FR-006 | Call-site gate for unlocked matrix writers | As a maintainer, I want an architectural gate over `src/` that fails when production code outside the seam calls `write_acceptance_matrix` or `write_and_commit_acceptance_matrix` (direct, attribute-style or aliased calls), with a shrink-only per-function allowlist, so that the lock is structurally unavoidable (#4887). | High | Open | [build] | no — self-mutation test plants an aliased call and an attribute-style call |
| FR-007 | accept-mission applies the host readiness verdict | As an external orchestrator, I want `orchestrator-api accept-mission` to call `collect_feature_summary` with `strict_metadata=True` and refuse with `MISSION_NOT_READY` when `summary.ok` is false, carrying `outstanding` (from `summary.outstanding()`), `activity_issues`, `skipped_checks` and `blocked_checks` (each `[{check, detail}]`) plus the mission identity fields, and to record acceptance only through the guarded record (FR-010) (#4934). | High | Open | [build] | no |
| FR-008 | CLI-level pin for missing lanes.json | As an operator, I want a CLI-level test proving `spec-kitty accept` exits non-zero and writes no `accepted_at` when `lanes.json` is absent, so that #4891's summary-level fix is pinned through the production entry point. | Medium | Open | [ratchet] | yes — positive control: the same fixture with `lanes.json` present and a passing matrix accepts |
| FR-009 | Orchestrator contract version | As an orchestrator author, I want `CONTRACT_VERSION` bumped to 1.7.0 with a ledger entry (`MIN_PROVIDER_VERSION` unchanged) and the accept-mission docs (`docs/api/orchestrator-api.md`, the orchestrator-api operator skill and its contract reference) updated with the new `MISSION_NOT_READY` cause and error data, so that the behavioural tightening is discoverable. | Medium | Open | [build] | no |
| FR-010 | Locked pre-stamp verdict re-check | As an operator, I want host `accept` and `accept-mission` to re-read the acceptance matrix under the status lock immediately before writing the acceptance record, and refuse unless the verdict is `pass` or `pass_pending_consolidation`, with the record write inside that lock span, so that a verdict committed between the gate and the stamp is never accepted over. | High | Open | [build] | no — positive control: no late verdict, accepts |
### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Short lock span | Negative-invariant verification commands and review-evidence population never run while the status lock is held; the locked span covers only re-read, splice, write and (for committing callers) commit. Verified by a lock-spy test. | Reliability | High | Open |
| NFR-002 | Bounded lock wait | The seam uses the existing bounded status-lock timeout (`BOUNDED_STATUS_LOCK_TIMEOUT_SECONDS`, 10 s) and never waits unbounded. | Reliability | High | Open |
| NFR-003 | Code quality | New and changed code passes `ruff check`, `ruff format --check` and `mypy` with zero findings; no function exceeds cyclomatic complexity 15; new branches reach ≥ 90% diff coverage. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | One readiness authority | Orchestrator-api acceptance reuses `collect_feature_summary` / `AcceptanceSummary.ok`; no second readiness computation. | Technical | High | Open |
| C-002 | Existing error code | Use the existing `MISSION_NOT_READY` error code; do not add an orchestrator error code (the vendored upstream contract pins `allowed_error_codes`). | Technical | High | Open |
| C-003 | `--no-commit` contract preserved | `accept --no-commit` still never creates a commit (HEAD unchanged); the gate's seam call uses the non-committing mode. | Technical | High | Open |
| C-004 | Same lock key everywhere | The seam locks on the matrix directory name, resolved once by the caller before any slow work, and reuses that directory for re-read and write (never re-derived). | Technical | High | Open |
| C-005 | Out of scope | Stay out of scope and go under the PR's Deferred section: matrix authoring (#4162, #4232, #5025); `--no-commit` side effects (#4089); converging `issue_verdict.py`'s twin helper into a generic status-lock primitive; the issue-matrix non-verdict writers; routing post-consolidation's re-judgement through the seam (`verify_deferred_invariants` has no production caller, so it is allowlisted with that rationale); the out-of-gate byte writers (`backfill_provenance.py` one-off migration, `merge_driver.py` git-invoked merge driver); the finalize-time scaffold's unlocked create-if-absent; accept-mission's uncommitted working-tree matrix write; the payload `mode: auto` label; a lenient accept-mission flag; the canceled-WP readiness difference; and the status-side TOCTOU in `populate_criteria_from_review_evidence`. | Business | Medium | Open |
| C-006 | No version numbers in scope | The mission does not assign a release version; the orchestrator `CONTRACT_VERSION` bump is a contract-ledger change, not a release version. | Business | Medium | Open |

### Key Entities

- **Acceptance matrix** (`acceptance-matrix.json`): per-mission criteria rows and negative-invariant rows with results; `overall_verdict` is derived from them.
- **Status lock**: the per-mission `feature_status_lock`, keyed on the mission directory name under the git common dir, shared by primary and coordination checkouts.
- **Acceptance summary**: the single readiness verdict (`AcceptanceSummary.ok`) with outstanding, skipped and blocked checks.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the #4974 reproduction through the `accept` CLI (NI and criterion variants, verdict recorded by the real `acceptance-verdict` command from a wrapped negative-invariant runner), accept exits non-zero, `meta.json` has no `accepted_at`, and the committed failing verdict is present on disk and in HEAD afterwards. Reverting FR-003 alone or FR-004 alone turns it red. The positive control on the same fixture accepts. — [build] · no-op passable: no
- **SC-005**: A failing verdict recorded after the gate's splice but before the acceptance record (injected by wrapping the record write) makes accept and accept-mission refuse with no `accepted_at`; without it, the same fixture accepts. — [build] · no-op passable: no
- **SC-006**: A holder of the mission status lock makes `accept` fail closed with a lock diagnostic and no matrix write; without the holder, the same fixture accepts. — [build] · no-op passable: no
- **SC-002**: The call-site gate reports zero unallowlisted raw acceptance-matrix writers in `src/`, and its self-mutation test proves it detects an injected raw call. — [build] · no-op passable: no
- **SC-003**: `orchestrator-api accept-mission` on a pending-matrix mission and on a no-`lanes.json` mission exits non-zero with `MISSION_NOT_READY`; `meta.json` gains no `accepted_at`, `acceptance_mode` or `acceptance_history` and HEAD is unchanged. The same acceptable fixture (lanes.json present, passing matrix) is accepted. — [build] · no-op passable: no
- **SC-004**: Each issue-pinned regression test for a [build] requirement is RED on the planning base and GREEN on the final commit; [ratchet] tests are GREEN on both. — [build] · no-op passable: no
