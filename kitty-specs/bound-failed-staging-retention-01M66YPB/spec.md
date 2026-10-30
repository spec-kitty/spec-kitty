# Mission Specification: Bound failed-synthesis staging retention

**Mission Branch**: `issue-6723-bound-failed-staging-retention`
**Created**: 2026-10-30
**Status**: Draft
**Input**: Issue spec-kitty/spec-kitty#6723 — "charter synthesize keeps one `.staging/<run_id>.failed/` directory per refused run, with no bound"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A repeatedly-refused synthesis stops filling the tree (Priority: P1)

An operator (or an agent following the implement gate's "run `spec-kitty charter synthesize`" remedy) runs `spec-kitty charter synthesize` and it is refused. The refusal preserves the run's staging directory as `.kittify/charter/.staging/<run_id>.failed/` so the failure can be diagnosed, then the command exits non-zero. The operator fixes part of the problem and runs it again, and again. Each refusal still preserves its own failure, but the number of preserved failures stops growing: only the newest few remain on disk.

**Why this priority**: This is the reported defect. Without it the project accumulates junk without limit, fastest exactly while someone is diagnosing a refusal (#4226 counted 15, then 16, on one repository).

**Independent Test**: Run six refusals against one project and count `.kittify/charter/.staging/*.failed/` — the count stays at the stated bound instead of six, and the newest failure's `cause.yaml` is still readable.

**Acceptance Scenarios**:

1. **Given** a project with no failed staging directory, **When** a `synthesize` run is refused, **Then** exactly one `.staging/<run_id>.failed/` directory exists and contains `cause.yaml`.
2. **Given** a project that already holds the maximum number of failed staging directories, **When** another run is refused, **Then** the new failure is kept, the oldest is removed, and the total number stays at the maximum.
3. **Given** a project holding more failed staging directories than the maximum (for example created by an older version), **When** the next run is refused, **Then** the tree is brought down to the maximum, not merely held at its current size.

---

### User Story 2 - The latest refusal is always diagnosable (Priority: P1)

An operator reads the newest failure to understand why synthesis was refused. The pruning never removes the failure the current command just preserved, and it never removes the newest preserved failure, so the message "Staging directory preserved at …" always names a directory that still exists when the command exits.

**Why this priority**: Diagnosis is the entire reason failed directories exist; a retention bound that can delete the failure being reported would be worse than the unbounded growth.

**Independent Test**: Refuse a run with the maximum already reached; the path named in the CLI output exists, holds `cause.yaml`, and its reason matches that run's failure.

**Acceptance Scenarios**:

1. **Given** the maximum number of failed staging directories is already present, **When** a new run is refused, **Then** the directory named in the refusal output exists after the command returns.
2. **Given** a run that fails for cause A after a run that failed for cause B, **When** both have been preserved and the bound is enforced, **Then** the newest (cause A) directory and its `cause.yaml` reason are intact.

---

### User Story 3 - A live run's staging directory is never disturbed (Priority: P2)

An operator has one synthesis run in progress (or a second process does) while another run is refused. The retention pass removes only preserved failures; the in-progress `.staging/<run_id>/` directory that the running command still needs is untouched.

**Why this priority**: Retention is a cleanup, not a licence to delete a live run's workspace. Getting this wrong turns a cosmetic defect into data loss mid-synthesis.

**Independent Test**: With a non-`.failed` staging directory present alongside more preserved failures than the bound, trigger one refusal; the non-`.failed` directory and its contents are unchanged.

**Acceptance Scenarios**:

1. **Given** an in-progress `.staging/<run_id>/` directory with content, **When** another run is refused and the bound is enforced, **Then** the in-progress directory and its files are unchanged.
2. **Given** entries under `.staging/` that are not failed-run directories, **When** the bound is enforced, **Then** they are left alone.

---

### Edge Cases

- **Fewer failures than the bound**: nothing is deleted; the bound only bites at the limit.
- **More failures than the bound already on disk**: the next refusal brings the count down to the bound (it does not merely prevent growth).
- **Several failures with the same modification time** (a test fixture, or a restored tree): the ordering is still deterministic, so the same directories survive each time.
- **Deletion fails** (permissions, a file locked by another process, a race with an operator reading a directory): the refusal still reports its real cause and the unremovable directory stays — retention never raises over the synthesis failure.
- **A run is refused while another is being written**: only `*.failed` entries are candidates; a directory still being populated is never a candidate.
- **`charter resynthesize` refusals**: same lifecycle, same bound — the fix lives in the shared staging lifecycle, not in one command.
- **A project that already has 15+ failed directories** (#4226): the next refusal prunes to the bound.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Requirement | Status | Delivery | No-op passable? |
|----|-------------|--------|----------|-----------------|
| FR-001 | After a refused synthesis run has preserved its own failure directory, the tool keeps only the newest 3 failed staging directories under `.kittify/charter/.staging/` and removes the rest. | Open | [build] | no |
| FR-002 | The failure preserved by the current run is never removed by the retention pass, whatever the ordering, and its `cause.yaml` (reason, traceback, timestamp) is intact when the command exits. | Open | [build] | no |
| FR-003 | The retention pass only considers directories whose name marks a preserved failure (`*.failed`); an in-progress staging directory, and any other entry under `.staging/`, is never removed. | Open | [build] | no |
| FR-004 | The retention pass tolerates more than the bound already present: an overflowing tree is reduced to the newest 3, not held at its current size. | Open | [build] | no |
| FR-005 | Removal goes through the existing guarded filesystem seam for the synthesizer; no new allowed-write prefix and no unguarded deletion primitive is introduced. | Open | [ratchet] | no |
| FR-006 | A failure while listing or removing older failed directories never raises over the synthesis failure: the command still reports the real refusal and exits non-zero, and any directory it could not remove simply stays. | Open | [build] | no |
| FR-007 | The refusal hint that names the preserved staging directory states that older failed directories are pruned and the number kept, so the operator knows why earlier copies disappeared. | Open | [build] | no |
| FR-008 | The number kept is a single named default in the staging lifecycle module, read by both the retention pass and the operator-facing text, so the stated number cannot drift from the enforced number. | Open | [build] | no |
| FR-009 | The governance-files reference for `.kittify/charter/.staging/` and the atomicity ADR describe the retention bound instead of implying failed directories are kept indefinitely. | Open | [build] | no |

### Non-Functional Requirements

| ID | Requirement | Status | Threshold |
|----|-------------|--------|-----------|
| NFR-001 | Retention adds no measurable delay to a refusal: it inspects at most the entries of one directory and removes one tree per excess failure. | Open | ≤ 50 ms added for a `.staging` root holding 100 failed directories on the test host |
| NFR-002 | Retention is bounded in the number of entries it touches and never walks into preserved failure contents to decide what to remove. | Open | one directory listing plus a metadata stat per candidate; no recursive walk |
| NFR-003 | Retention is fail-safe: when it cannot complete, directories stay rather than being half-removed, and the synthesis failure is still the reported error. | Open | 100% of refusal paths and their exit code unchanged |
| NFR-004 | No new runtime dependency, configuration key or environment toggle is introduced. | Open | dependency manifest and config schema unchanged by this mission |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|--------|--------|
| C-001 | Issue scope only | Address #6723's retention bound. Do not change synthesis, validation, promotion, `cause.yaml` contents or the collision remedy from #6510; do not add a configuration knob or a new command. | Scope | High | Open |
| C-002 | One staging lifecycle authority | The fix belongs in `src/charter/activation/synthesizer/staging.py` (the `StagingDir` lifecycle) so `synthesize`, `resynthesize` and the orchestrator paths all inherit it; no second retention implementation elsewhere. | Architecture | High | Open |
| C-003 | Guarded deletion | Every removal goes through `PathGuard` (the synthesizer's declared write seam); the ADR's "staging writes go through PathGuard" invariant and its existing path-guard test stay true. | Architecture | High | Open |
| C-004 | Red-first proof | A failing test through the pre-existing entry point lands before the production change, and the red-to-green transition is recorded in the PR. | Quality | High | Open |
| C-005 | PR-only delivery | Work stays on the dedicated issue branch; a draft PR to `main`, green and flipped to ready for review, is the terminal state. Nothing is merged by the implementer. | Workflow | High | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Six consecutive refusals on one project leave exactly 3 failed staging directories, not 6. — [build] · no-op passable: no
- **SC-002**: The failed directory named in the newest refusal's output exists and its `cause.yaml` reason identifies that refusal. — [build] · no-op passable: no
- **SC-003**: A pre-existing overflow of failed staging directories is reduced to 3 by the next refusal. — [build] · no-op passable: no
- **SC-004**: An in-progress staging directory with content survives a retention pass byte-identical. — [build] · no-op passable: no
- **SC-005**: Every refusing run still exits non-zero and reports its own error when retention cannot remove a directory. — [build] · no-op passable: no
- **SC-006**: The number stated to the operator matches the number enforced by the retention pass (one source). — [build] · no-op passable: no
- **SC-007**: The existing synthesizer suite (staging atomicity, write pipeline, path guard) keeps passing unchanged. — [ratchet] · no-op passable: yes — paired with SC-001's new-behaviour check

## Key Entities *(include if the mission involves data)*

- **Failed staging directory**: `.kittify/charter/.staging/<run_id>.failed/`, a refused run's preserved workspace with a `cause.yaml` (reason, traceback, timestamp). Diagnostic evidence, gitignored, not authored content.
- **In-progress staging directory**: `.kittify/charter/.staging/<run_id>/`, the live workspace of a running synthesis; never a retention candidate.
- **Retention bound**: the number of failed staging directories preserved — 3, owned by one named default in the staging lifecycle module.

## Assumptions and Dependencies

- The run identifier is a ULID (monotonic, sortable), and directory modification time is a truthful recency signal on a normal filesystem; the retention ordering uses recency with a deterministic tiebreak rather than trusting a name pattern.
- `.kittify/charter/.staging/` is gitignored and inside the guarded write surface, so no ignore-list or allowlist change is needed.
- The refusal path is shared: `synthesize`, `resynthesize` and the orchestrator all use the same `StagingDir` context manager, so one change covers them.
- The issue's "for example" retention shapes are guidance, not a fixed contract; the bound (3) and its stated rationale are recorded in `research.md` and the resolved Decision Moment `01M66YQ2ZWJ6KDAH59GTBB24YM`.
