# Mission Specification: Truthful verdicts and gates

**Mission Branch**: `issue-6652-verdict-gate-truthfulness`
**Created**: 2026-10-26
**Status**: Draft
**Input**: Operator dispatch (triage 2026-10-26, slice B): "verdicts and gates must not report something untrue" — #6652, #6654, #6653, #6649; #5393 pulled in.

## Intent Summary (confirmed)

Confirmed by the operator on 2026-10-26 (Decision Moments `01M5X10Z…`, `01M5X114…`, `01M5X11A…`, `01M5X11F…`).

- **Primary actors:** a reviewer recording a work package verdict with `move-task`; an operator consolidating a Mission under `merge_gates.mode: block`; anyone committing files with `safe-commit`.
- **Trigger and outcome:** each of these commands reports what happened. When it says something was persisted, checked or committed, that is true; when it cannot do the thing, it says so.
- **Rule that must always hold:** no command reports success, durability or a clean gate for something it did not do or did not check.
- **Out of scope:** changing how rejections are recorded, the approval-stamp bound, the issue-reference detector's one-digit rule, and `safe-commit` directory expansion of an ignored directory (it follows the documented "changed/untracked files" rule).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An approval keeps the reviewer's written review (Priority: P1)

A reviewer approves a work package and passes a review file with `--review-feedback-file`. Today the file is validated, then discarded, and the command reports the verdict as durably persisted.

**Why this priority**: the review record is the traceability evidence for an approval; losing it while reporting success is the defect the operator ranked first (#6652, P1, 4.0.0 release scope).

**Independent Test**: approve a work package with a feedback file holding a distinctive line, then read the approval's review-cycle record.

**Acceptance Scenarios**:

1. **Given** a work package in review, **When** the reviewer approves it with a feedback file, **Then** the approval's review-cycle record contains the approval line and the file's full content, and the reported `review_feedback` pointer leads to that record.
2. **Given** a work package in review, **When** the reviewer approves it without a feedback file, **Then** the record is the same one-line approval it is today.
3. **Given** a work package whose latest verdict is already an approval, **When** it moves on with a feedback file, **Then** a new approved review-cycle record carrying the file is written; **When** it moves on without one, **Then** nothing new is written.
4. **Given** a feedback file that is itself a prior review-cycle record, **When** it is passed on an approval, **Then** the command refuses it, as it does for a rejection.

---

### User Story 2 - The recorded replay command replays (Priority: P1)

The approval record carries a `reproduction_command`. With a reviewer named `Jane Doe (model-x)` the command is not valid shell and splits the reviewer into three words (#6654).

**Independent Test**: approve with a multi-word reviewer holding shell metacharacters, then split the recorded command as a shell would.

**Acceptance Scenarios**:

1. **Given** a reviewer `Jane Doe (model-x)`, **When** the approval is recorded, **Then** splitting the recorded command yields `--agent` followed by exactly `Jane Doe (model-x)`, and the command parses as valid shell.
2. **Given** a single-word reviewer, **When** the approval is recorded, **Then** the command reads as it does today.

---

### User Story 3 - The terminality gate checks every row it reports on (Priority: P1)

Under `merge_gates.mode: block`, `consolidate` prints "No unresolved (in-mission/unknown) issue-matrix rows" and lands a Mission whose matrix still has an `in-mission` row, when that row's issue is not a gating reference the Mission's artifacts cite (#6653).

**Independent Test**: record an `in-mission` row for an issue the spec does not cite, then run the done-gate and the consolidation gate.

**Acceptance Scenarios**:

1. **Given** a matrix with an `in-mission` row for an uncited issue and a cited issue with a terminal verdict, **When** the gate runs at done, **Then** it fails and names the row (blocking in `block` mode, warning in `warn` mode).
2. **Given** a Mission that cites no gating issue but has a matrix with an `in-mission` or unknown row, **When** the gate runs at done, **Then** it fails and names the row.
3. **Given** a Mission that cites no gating issue and has no matrix, **When** the gate runs, **Then** it passes, saying there were no gating references and no matrix; a coordination Mission with no matrix does not fail on the coordination probe.
4. **Given** the same `in-mission` row, **When** a work package moves to `approved`, **Then** it is not blocked (`in-mission` stays acceptable before done).

---

### User Story 4 - safe-commit commits a named ignored file or does not claim success (Priority: P2)

`safe-commit docs-local/a.md`, where `docs-local/` is gitignored and the file is the only changed path, exits 0 with `"result": "success"` and `"committed": false`. Named next to another changed file, the same file is committed (#6649). Directory expansion of non-ASCII names (#5393) is verified fixed on `main` and gets a command-level regression test.

**Independent Test**: name a lone new ignored file, then name it beside a changed tracked file; compare outcomes.

**Acceptance Scenarios**:

1. **Given** a new file under an ignored directory, **When** it is named alone, **Then** it is committed, exactly as when it is named beside another changed file.
2. **Given** a named file with no change, **When** it is named alone, **Then** the command still reports that nothing was committed.
3. **Given** a directory holding a new non-ASCII-named file, **When** the directory is named, **Then** the file is committed under its real name.

### Edge Cases

- A feedback file on an arbiter override into `approved` stays unrecorded as an approval (an arbiter override is never an approval record).
- An approval whose prior verdict slot is damaged stays a no-op; a supplied feedback file is then refused rather than dropped silently.
- An ignored *directory* named as an argument still expands to its changed, non-ignored files only.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Requirement | Status | Delivery | No-op passable? |
|----|-------------|--------|----------|-----------------|
| FR-001 | When an approval is given a feedback file, the approval's review-cycle record contains the approval line followed by the file's full content. | Accepted | build | no |
| FR-002 | Without a feedback file, the approval record stays the one-line approval it is today, and a repeated approval writes no duplicate record. | Accepted | ratchet | no — positive control is FR-001's fixture with the file omitted |
| FR-003 | A feedback file on an approval whose latest verdict is already approved writes a new approved review-cycle record carrying the file. | Accepted | build | no |
| FR-004 | A feedback file that is a prior review-cycle record is refused on an approval, as on a rejection. | Accepted | build | no |
| FR-005 | When an approval cannot record a supplied feedback file (damaged verdict slot), the command refuses instead of reporting success. | Accepted | build | no |
| FR-006 | The approval's recorded replay command quotes every interpolated value, so a shell split yields the reviewer as one argument. | Accepted | build | no |
| FR-007 | At done, the issue-matrix terminality check fails for any `in-mission` row in the matrix, whether or not its issue is a cited gating reference. | Accepted | build | no |
| FR-008 | At done, a Mission with no gating references but an existing matrix has the whole matrix evaluated (in-mission and unknown/invalid rows fail). | Accepted | build | no |
| FR-009 | A Mission with no gating references and no matrix passes the terminality gate with a message saying so, without failing on the coordination probe. | Accepted | ratchet | no — positive control is FR-008's fixture with the matrix removed |
| FR-010 | Before done (`approved`), an `in-mission` row stays non-blocking. | Accepted | ratchet | no — paired with FR-007's fixture at `done` |
| FR-011 | `safe-commit` commits an explicitly named new ignored file when it is the only path named, matching the result when it is named beside another changed path. | Accepted | build | no |
| FR-012 | `safe-commit` on a directory holding a new non-ASCII-named file commits that file under its real name (#5393). | Accepted | ratchet | no |

### Non-Functional Requirements

| ID | Requirement | Threshold | Status |
|----|-------------|-----------|--------|
| NFR-001 | Every defect is reproduced by a test that fails on the base commit before its fix lands. | 100% of FR rows marked build have a red-first test | Accepted |
| NFR-002 | Changed code passes the repository's lint, format and type checks with no new suppressions. | 0 new findings, 0 new suppressions | Accepted |
| NFR-003 | No touched function exceeds the complexity ceiling. | cyclomatic complexity ≤ 15 | Accepted |

### Constraints

| ID | Constraint | Status |
|----|------------|--------|
| C-001 | One pull request per defect group: #6652+#6654, #6653, #6649+#5393; each a draft targeting `main`. | Accepted |
| C-002 | Stay off the sibling slices' surfaces: the nightly reds (#6683, #6682), charter fail-open (#6454, #6417) and the LICENSE (#6478). | Accepted |
| C-003 | Rejection recording and the provenance guard's existing behaviour are unchanged. | Accepted |

### Key Entities

- **Review-cycle record**: the per-verdict artifact (`review-cycle-N.md`) a status event points to.
- **Issue-matrix row**: one issue's verdict in the Mission's issue matrix; `in-mission` is non-terminal.
- **Gating reference**: an issue citation the reference detector classifies as an implementation target.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A reviewer's approval feedback text appears in the approval record in 100% of approvals given a feedback file. — [build] · no-op passable: no
- **SC-002**: A recorded approval replay command reproduces the same reviewer attribution for any reviewer name. — [build] · no-op passable: no
- **SC-003**: No Mission lands with an `in-mission` row while the terminality gate reports a pass. — [build] · no-op passable: no
- **SC-004**: A file named to `safe-commit` gets the same outcome whatever else is named in the call. — [build] · no-op passable: no

## Assumptions

- The approval line keeps the approval reference in the record (the executor's comment relies on it), so the feedback content follows it rather than replacing it.
- #5393's comment of 2026-10-07 is accurate that `main` already decodes the path; this mission adds only the regression test and closes it.
