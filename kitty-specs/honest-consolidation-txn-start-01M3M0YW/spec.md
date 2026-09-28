# Mission Specification: Honest consolidation transaction start + nightly integration green

**Mission Branch**: `issue-5111-honest-consolidation-txn-start`
**Created**: 2026-09-28
**Status**: Draft
**Input**: Issues #5111 (first, red-first), #5044 → closes #5045 and the `test_merge_resume` half of #5049, plus #5110.

## Context

A fresh `spec-kitty consolidate` persists its transaction record (`state.json`, in
`_load_or_create_merge_state`, `consolidation/resolve.py`) **before** the merge gates
run (`_phase_gates_and_state`), but writes the FR-012 reconciliation marker only
**afterwards** (`_capture_reconciliation_claim`, `consolidation/executor.py`). Any exit in
that window — "Merge gates failed", the canonical-history guard, a declined hollow-review
confirmation — leaves a marker-less `state.json`. The operator's next plain
`spec-kitty consolidate` loads it as a resume and `detect_legacy_in_flight_state`
refuses it as a "pre-fix in-flight merge state", although nothing was ever mutated
(#5111). Reproduced RED through the real CLI on `af847be7`.

Separately, the nightly `integration` lane (`tests/integration`, no per-PR lane) is red:
22 failures on dispatch run 36393904544, all reproduced locally (#5044/#5045). Five
fixture drifts (A–E in the #5045 squad comment) follow deliberate product changes
(#4959, #5001, #4764, #4758, #4990); one red (`test_sc007_in_review_to_in_progress_is_force_free`)
is new and needs an operator verdict. The perf-suite `test_resume_completes_within_30s_budget`
(#5049) shares drift C1.

Finally, `consolidate --dry-run` crashes with a raw traceback when the coordination
worktree is unmaterialized (#5110): `CoordinationWorktreeUnmaterialized` derives from
`StatusReadPathNotFound(Exception)` and escapes `except (RuntimeError, OSError)` in
`consolidation/forecast.py`. Reproduced RED through the real CLI.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A failed fresh consolidate can simply be re-run (Priority: P1)

An operator runs `spec-kitty consolidate`; a merge gate fails. They fix the cause and
run `spec-kitty consolidate` again. The re-run evaluates the gates and proceeds — it is
not refused as a pre-fix in-flight state and does not require `--abort`.

**Why this priority**: today the only escape is `--abort` plus manual verification, which
the refusal text presents as a possible corruption event. This wedges ordinary retries.

**Independent Test**: `tests/consolidation/test_issue_5111_fresh_gate_failure_rerun.py`
drives the real `consolidate` CLI twice (gate verdict failing, then passing).

**Acceptance Scenarios**:

1. **Given** an approved coord mission, **When** a fresh `consolidate` fails at "Merge gates failed" and the operator re-runs `consolidate` without flags, **Then** the re-run evaluates the gates again, is not refused as pre-fix, and proceeds past claim capture.
2. **Given** a fresh run that failed at a gate, **When** the operator runs `consolidate --abort`, **Then** both `state.json` and the reconciliation marker are removed.
3. **Given** a genuinely pre-fix in-flight state (state without marker, written by older code), **When** consolidate resumes, **Then** it is still refused (FR-012 unchanged).

### User Story 2 - The dry run fails closed on an unmaterialized coord worktree (Priority: P2)

An operator (or CI) runs `consolidate --dry-run [--json]` on a coord mission whose
coordination worktree is not checked out. They get exit 1, the exception's own
remediation text, and — with `--json` — a valid JSON error object.

**Independent Test**: `tests/consolidation/test_issue_5110_dry_run_unmaterialized_coord.py`.

**Acceptance Scenarios**:

1. **Given** an unmaterialized coord worktree, **When** `consolidate --dry-run`, **Then** exit 1 with a readable message naming the unmaterialized worktree and no traceback.
2. **Given** the same, **When** `consolidate --dry-run --json`, **Then** exit 1 and stdout's last line parses as JSON with `error` and `error_code == COORDINATION_WORKTREE_UNMATERIALIZED`.

### User Story 3 - The nightly integration lane tells the truth (Priority: P2)

Every #5044 `tests/integration` red is either green (stale fixture re-pinned to the
current contract) or carries a written, operator-verdicted disposition. No test is
skipped, quarantined, or retried to green.

**Independent Test**: the 12 affected integration files run green except any
explicitly verdicted-and-documented red.

**Acceptance Scenarios**:

1. **Given** a red caused by a deliberate product change, **When** the fixture is re-pinned, **Then** the test still fails if the behaviour it guards regresses (no vacuous re-pin).
2. **Given** `test_sc007_in_review_to_in_progress_is_force_free`, **When** no operator verdict is obtained, **Then** it stays red and the PR documents both sides.

### Edge Cases

- Crash between marker write and state write: an orphan marker without state must be harmless (no state ⇒ fresh run, which re-stamps the marker).
- `clear_state(repo, mission_id)` on a runtime dir holding only an orphan marker: removes the marker, returns `False` (no state was cleared).
- Legacy state migrated to the canonical key in `_load_or_create_merge_state` is a *loaded* state (resume) and must not be marker-stamped by this fix (FR-012 must keep refusing genuinely pre-fix state).
- `CoordinationBranchDeleted` (sibling of the unmaterialized error) in the dry run gets the same fail-closed treatment.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Fresh state implies marker | As an operator, I want a fresh transaction's `state.json` never to be on disk without its reconciliation marker so that a re-run after any pre-mutation failure is recognised as post-fix. | High | Open | [build] | no — RED on `af847be7` via the real CLI (US1 AS1) |
| FR-002 | Clearing the transaction clears the marker | As an operator, I want `clear_state(repo, mission_id)` (used by `--abort` and finalize) to remove the marker with the state so that a leftover marker never vouches for a later, unrelated state. | High | Open | [build] | no — RED unit + CLI `--abort` test |
| FR-003 | Pre-fix refusal preserved | As a maintainer, I want a genuinely marker-less resumed state to still be refused so that FR-012 of the terminus mission holds. | High | Open | [ratchet] | yes — paired with FR-001 on the same fixture shape (existing `detect_legacy_in_flight_state` tests) |
| FR-004 | Dry run fails closed on coord read-path errors | As an operator, I want `consolidate --dry-run` to exit 1 with the exception's remediation (and valid `--json`) when the coord worktree is unmaterialized or the coord branch deleted so that the preview never crashes. | Medium | Open | [build] | no — RED via the real CLI |
| FR-005 | Integration reds dispositioned | As a release owner, I want every #5044 `tests/integration` red re-pinned (stale fixture) or fixed (real regression) with a DIRECTIVE_041 classification so that the nightly integration lane goes green honestly. | High | Open | [ratchet] | no — each test is RED at base |
| FR-006 | Resume budget test green | As a release owner, I want `test_resume_completes_within_30s_budget` green by re-pinning its C1 fixture, not by loosening the budget. | Medium | Open | [ratchet] | no — RED at base |
| FR-007 | sc007 verdict | As the operator, I want a both-sides write-up for `test_sc007_in_review_to_in_progress_is_force_free` and to rule on it before any edit; absent a ruling it stays red and is documented. | Medium | Open | [folded] | yes — documentation outcome |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No weakening | Zero `skip`/`xfail`/quarantine/retry additions; zero loosened time budgets. | Reliability | High | Open |
| NFR-002 | Code quality | Touched functions stay at complexity ≤ 15; `ruff check`, `ruff format --check`, `mypy` clean on touched files. | Maintainability | High | Open |
| NFR-003 | Coverage | New/changed product lines covered by tests in the same PR (diff-cover ≥ 90%). | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Sibling ownership | Do not edit `.github/workflows/ci-nightly.yml`, `scripts/ci/nightly_escalation.py`, `tests/charter/test_consistency_check.py` (slice 2), `tests/specify_cli/**` or doctor/decision goldens (slice 3). | Process | High | Open |
| C-002 | No full heavy suites | Targeted files only; never `make test-full` or bare `tests/architectural/` (`NO_FULL_HEAVY_SUITES_IN_MISSION`). | Process | High | Open |
| C-003 | Operator merges | PR against `main`, labelled `ready-for-squad` when complete; never merged by the implementer. | Process | High | Open |
| C-004 | No `spec_kitty_events` edits | Drift E is fixed on the fixture side; the events reducer is out of scope. | Technical | Medium | Open |

### Key Entities

- **Consolidation transaction record**: the per-mission runtime dir `.kittify/runtime/merge/<mission_id>/` holding `state.json` and the `reconciliation.post-fix` marker. They are created and cleared together.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A fresh `consolidate` that fails at a gate followed by a plain re-run reaches the gates again and proceeds (CLI test green; RED at base) — [build] · no-op passable: no
- **SC-002**: `consolidate --dry-run [--json]` on an unmaterialized coord worktree exits 1 and emits valid JSON (CLI tests green; RED at base) — [build] · no-op passable: no
- **SC-003**: 21 of 22 #5044 integration reds green; the 22nd (`sc007`) carries a verdicted or documented disposition — [ratchet] · no-op passable: no
- **SC-004**: `test_merge_resume::test_resume_completes_within_30s_budget` green with its budget unchanged — [ratchet] · no-op passable: no
