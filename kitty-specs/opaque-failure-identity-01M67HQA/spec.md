# Mission Specification: Opaque declared-command failure identity

**Mission Branch**: `issue-6751-opaque-failure-identity`
**Created**: 2026-10-30
**Status**: Draft
**Input**: Issue spec-kitty/spec-kitty#6751 — "[bug] Opaque declared-command failures collide across baseline and candidate, yielding no_new_failures".

The pre-review regression gate compares a candidate run against a baseline captured on the base commit. For a repo that declares its own test command, unparseable (opaque) nonzero results are represented by one synthetic identity, `<declared-command>` (`review/scope_source.py::_whole_run_failure`). `review/baseline.py::diff_baseline` matches failures by `test` name only, so **any** opaque baseline failure matches **any** opaque candidate failure, and `pre_review_gate.py::_classify_current_failures` returns `no_new_failures`. A genuine regression — the candidate failing for a completely different reason than the baseline — is classified as green. Reproduced on `main@512567eee7` with the issue's own snippet: baseline `error: no build.zig file found ...` (exit 2) vs candidate `src/example.zig:1:1: error: expected type 'u64', found '[]const u8'` (exit 1) yields `outcome=no_new_failures`, `new_failure_count=0`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A regression is never classified as a pass (Priority: P1)

A maintainer moving a work package to review relies on the pre-review gate to tell a pre-existing failure from a newly introduced one. When both the baseline and the candidate fail opaquely — the declared command exited nonzero with no parseable per-failure identity — the two failures are only the same failure if they are actually the same: same exit status and same summary. A candidate opaque failure that differs from the baseline's must be reported as a new failure, never as `no_new_failures`.

**Why this priority**: The gate is a regression detector. An identity placeholder that matches everything turns the gate into a rubber stamp and can hand a real regression to a reviewer as green.

**Independent Test**: The issue's counterexample (missing `build.zig` baseline vs. a compilation-error candidate) returns `new_failures`; the same fixture with an identical opaque baseline returns `no_new_failures` with one pre-existing failure. Both assertions run on the same fixture.

**Acceptance Scenarios**:

1. **Given** a baseline whose declared command failed opaquely with `exit 2` and `error: no build.zig file found ...`, **When** the candidate fails opaquely with `exit 1` and a different summary, **Then** the verdict is `new_failures` and the candidate failure is listed as new.
2. **Given** the same baseline, **When** the candidate fails opaquely with the identical exit status and summary, **Then** the verdict is `no_new_failures` and that failure is listed as pre-existing.
3. **Given** the same summary but a different exit status, **When** the candidate result is classified, **Then** it is a new failure (the opaque identity is not established).

### User Story 2 - The verdict says what the candidate command actually did (Priority: P2)

An operator reads the recorded verdict to decide whether a `no_new_failures` verdict means "the suite ran clean" or "the suite failed, but only in ways the baseline already had". Today the verdict carries no exit status, so a failing candidate and a clean candidate are indistinguishable. The verdict must carry the candidate run's observed exit status, and the `no_new_failures` reason must state that the verdict is baseline-relative and does not assert a clean exit.

**Why this priority**: The issue's real incident had a separately proven exit-0 candidate, but the gate's own output could not establish it. Removing that ambiguity is what stops `no_new_failures` from masquerading as a pass.

**Independent Test**: A gate evaluation whose declared command exits nonzero with only pre-existing named failures yields `no_new_failures` whose verdict carries the exit status and whose reason names it.

**Acceptance Scenarios**:

1. **Given** a candidate declared command that exits `2` with a failure already present in the baseline, **When** the gate classifies it, **Then** the verdict is `no_new_failures`, `candidate_exit_code == 2`, and the reason says the result is baseline-relative, not a clean exit.
2. **Given** a candidate declared command that exits `0` with no failures, **When** the gate classifies it, **Then** the verdict is `no_new_failures` with `candidate_exit_code == 0` and no new or pre-existing failures.

### Edge Cases

- **Named failures unchanged.** `FAIL <name>: <message>` output yields a real per-failure name; the name remains the identity, so a pre-existing named failure with a changed message is still pre-existing, and a named failure absent from the baseline is still new.
- **JUnit artifact runs unchanged.** A parsed JUnit artifact yields named failures and is unaffected by the opaque rule.
- **Legacy baseline artifacts.** A `baseline-tests.json` written before this change (no opaque marker, no exit status) still loads without error; its opaque-looking entry is treated as an opaque failure of unknown exit status, so it cannot silently match a candidate run.
- **Mixed shapes.** A named candidate failure never matches an opaque baseline entry and vice versa, even if the text collides.
- **Uncomputable baseline.** `baseline is None` / `failed == -1` keeps yielding `unverified_baseline` (unchanged).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Opaque failures carry a bound identity | As a maintainer, I want an opaque declared-command failure to carry its observed exit status and summary as its comparable identity, so that two opaque failures are the same failure only when both match. | High | Open | [build] | no — the issue counterexample returns `no_new_failures` on the base commit |
| FR-002 | Same opaque failure stays pre-existing | As a maintainer, I want an opaque candidate failure identical to the baseline's to remain pre-existing, so that a repo whose declared command fails the same way before and after is not blocked. | High | Open | [ratchet] | no — paired with FR-001 on the same fixture (the pair is the positive control for each other) |
| FR-003 | Named identities keep name matching | As a maintainer, I want recognised `FAIL <name>` failures to keep name-based matching, so that the existing pre-existing-failure behaviour is preserved. | High | Open | [ratchet] | no — paired with a new-named-failure assertion on the same fixture |
| FR-004 | Verdict reports the candidate exit status | As an operator, I want the gate verdict to carry the candidate command's observed exit status and to say in its `no_new_failures` reason that the verdict is baseline-relative, so that `no_new_failures` cannot be read as a clean candidate exit. | High | Open | [build] | no — the base verdict carries no exit status and no reason |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Targeted surface only | The change is validated with the review test modules that own the touched code (`tests/review/`), never a full or heavy suite; changed lines meet the repository's 90% diff-cover bar. | Quality | High | Open |
| NFR-002 | Static checks clean | Changed files pass `ruff check`, `ruff format --check` and mypy with no new issues and no new suppressions. | Quality | High | Open |
| NFR-003 | Baseline artifact back-compat | An existing `baseline-tests.json` written before this change loads without `KeyError` and keeps its `source_identity` semantics. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No gate bypass or default change | No gate is skipped, xfailed, quarantined or retried, no timeout default changes, and the opt-in block semantics (`NEW_FAILURES` + `block_enabled` + `force`) are untouched. | Process | High | Open |
| C-002 | No pass for unparseable results | An unparseable nonzero candidate result must never be classified as a pass on identity alone; the only `no_new_failures` that may contain an opaque failure is one whose bound identity matches the baseline exactly, and its reason records the non-zero exit. | Technical | High | Open |
| C-003 | Locality of change | Product edits stay inside `src/specify_cli/review/{baseline,scope_source,pre_review_gate}.py` plus the transition-gate rendering that surfaces the verdict; no unrelated refactor. | Technical | Medium | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The issue's counterexample (missing-build baseline vs. different opaque candidate failure) returns `new_failures` with one new failure, and returns `no_new_failures` on the base commit. — [build] · no-op passable: no
- **SC-002**: On the same fixture, an identical opaque failure (same exit status and summary) returns `no_new_failures` with one pre-existing failure. — [ratchet] · no-op passable: no
- **SC-003**: A recognised named failure present in the baseline stays pre-existing while a named failure absent from the baseline is new; both asserted on one fixture. — [ratchet] · no-op passable: no
- **SC-004**: A `no_new_failures` verdict reached from a candidate run that exited nonzero carries that exit status and a reason that says the verdict is baseline-relative. — [build] · no-op passable: no
- **SC-005**: A genuinely successful candidate (exit 0, no parseable failures) still returns `no_new_failures` with no failures, and a JUnit-artifact run still diffs by test name. — [ratchet] · no-op passable: no
