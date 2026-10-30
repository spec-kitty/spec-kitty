# Mission Specification: Review feedback draft retirement

**Mission Branch**: `review-feedback-draft-retirement-01M66YR3`
**Created**: 2026-10-30
**Status**: Draft
**Input**: GitHub issue spec-kitty/spec-kitty#6632 — "[bug] review rejection leaves review-feedback-N.md untracked; the next move-task refuses"

## Problem

The review prompt tells a rejecting reviewer to write feedback to
`kitty-specs/<mission>/tasks/<wp-dir>/review-feedback-N.md`, described as "in-repo, committed with
the project", and promises that "The Python script handles all file updates automatically". The
printed rejection command (`move-task <WP> --to planned --review-feedback-file <that path>`) writes
and commits `review-cycle-N.md` — a frontmatter header plus the source's body, byte for byte — and
then neither commits nor removes the source.

The draft stays untracked in the repository root checkout. The work package's next
`move-task --to for_review` refuses on it, because the planning-artifact check
(`tasks_parsing_validation.py::_validate_research_artifacts`) counts
`tasks/<wp-dir>/review-feedback-N.md` as that work package's own uncommitted work
(`review/dirty_classifier.py::owning_wp_for_path`). `spec-kitty accept` reports the same file as
`git_dirty`. The workflow therefore dead-ends on its own output: the operator has to run a
`safe-commit` that is broader than the problem (the issue's own workaround swept mission status
state into the commit). Reproduced end-to-end on current `main` through the real CLI before this
spec was written (see `traces/approach.md`).

## Decision: retire the draft, do not commit it

#6632 offers two repairs: commit the source alongside the record, or treat the source as a draft
and remove it once the record is durable. The mission takes the second, because the first is
actively unsafe in the coordination topology this mission itself runs on. The first issue comment
documents the failure: committing `review-feedback-N.md` on the coordination branch carries the file
onto the lane branch when the work package is re-claimed, `move-task` then refuses a `kitty-specs/`
file committed on a lane, and the implementer's printed remedy (delete it on the lane) is carried to
the target branch by the squash in `consolidate` — the reviewer's text is then gone. Retiring the
draft leaves nothing to commit onto a lane and nothing to delete later.

Nothing is lost by removing it: the record `review-cycle-N.md` already carries the source body
verbatim, and the retirement only runs after the commit is **durable** (read back from the
destination ref and byte-compared — the existing `_commit_review_cycle_artifact` proof).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A rejection leaves the tree clean (Priority: P1)

A reviewer rejects a work package by writing feedback at the path the review prompt advertised and
running the rejection command the prompt printed. Afterwards the mission directory is clean, and the
implementer's next `move-task --to for_review` passes the planning-artifact check without a manual
commit.

**Why this priority**: This is the reported defect. Without it the review loop cannot complete a
rejection cycle at all on the printed commands.

**Independent Test**: Drive a fixture mission through `in_review` → `move-task --to planned
--review-feedback-file <advertised path>` → `move-task --to for_review` through the real CLI, with
`_validate_research_artifacts` NOT stubbed out, and assert both commands exit 0 and
`git status --porcelain kitty-specs/<mission>/` is empty.

**Acceptance Scenarios**:

1. **Given** a work package in `in_review` and feedback written at
   `kitty-specs/<mission>/tasks/<wp-dir>/review-feedback-1.md`, **When** the reviewer runs the
   printed rejection command, **Then** it exits 0, `review-cycle-1.md` is committed, and
   `git status --porcelain kitty-specs/<mission>/` reports no `review-feedback-1.md` entry.
2. **Given** that clean tree and the implementer's rework committed, **When** the implementer runs
   `move-task <WP> --to for_review`, **Then** it is not refused for `Blocking: 1 uncommitted file(s)`
   naming the reviewer's draft.
3. **Given** the recorded `review-cycle-1.md`, **When** a reader opens it, **Then** it still contains
   the reviewer's text verbatim.

### User Story 2 - The repair never destroys feedback (Priority: P1)

When the record is not durable, or the draft is not the transient file this mission may remove, the
draft is left exactly where it is.

**Why this priority**: A repair that can silently delete a reviewer's only copy of a finding would be
worse than the bug. #3044 (a negative verdict's own text not reaching its consumer) is the standing
hazard this guards.

**Independent Test**: Same fixture, one parameter changed per case: `--no-auto-commit` (record not
durable), a draft committed by the reviewer before the rejection (tracked), a draft outside the
mission directory (`/tmp`), and a draft edited between read and removal. Each case asserts the file
still exists with its content.

**Acceptance Scenarios**:

1. **Given** `--no-auto-commit`, **When** the rejection runs, **Then** the draft remains on disk.
2. **Given** a draft the reviewer already committed, **When** the rejection runs, **Then** the draft
   remains tracked and unmodified (removing it would itself dirty the tree).
3. **Given** a draft outside `kitty-specs/<mission>/`, **When** the rejection runs, **Then** it is
   untouched.
4. **Given** a draft whose bytes changed after the record was written from it, **When** retirement
   would run, **Then** the draft is kept and the mismatch is reported.

### User Story 3 - The prompt describes what the command does (Priority: P2)

A reviewer reading the review prompt learns the truth about the file: it is a draft, the derived
record keeps its text, and the rejection command removes it once the record is committed.

**Why this priority**: The prompt's "committed with the project / handles all file updates
automatically" claim is what made the leftover look acceptable. #3430 already showed that a prompt
promising something the command does not do costs a whole review cycle.

**Independent Test**: Build a review prompt and assert it no longer claims the draft is committed
with the project, names the record that keeps the text, and says the draft is removed when the record
is durable.

**Acceptance Scenarios**:

1. **Given** the `REVIEW: <WP>` prompt, **When** rendered, **Then** its rejection section says the
   file is a draft the rejection command records and then removes, and does not say it is committed.

### Edge Cases

- The reviewer passes the tool's own record (`review-cycle-N.md`) as `--review-feedback-file`: the
  existing provenance guard still refuses it; this mission adds no new path.
- The feedback file does not exist, is a directory, or is empty: unchanged behaviour — the existing
  typed errors are raised before any write.
- The draft is a symlink into the mission directory: only the link is removed, never its target.
- The draft sits inside the mission directory but under another work package's directory: the
  `--review-feedback-file` source of this move is what is retired, whichever directory it names.
- The record is adopted from a prior run (identical bytes already committed, `adopted=True`): the
  verdict is durable, so the draft is still retired.
- The transition that follows the durable write fails and the record is reverted: the draft has
  already been retired, so the reviewer must re-supply the feedback. This is the same information
  position as before the fix (the record was reverted either way) and is named in the docs entry.
- Two rejections in a row (cycles 1 and 2): each retires its own draft; no draft accumulates.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Retire the consumed draft on a durable record | As a reviewer, I want my feedback draft gone once it is safely recorded so that the tree stops blocking the loop. | High | Open | [build] | no — positive control: the same fixture with the record not durable keeps the file (FR-002) |
| FR-002 | Keep the draft when the record is not durable | As a reviewer, I want my only copy kept when the write was not persisted so that no finding is lost. | High | Open | [build] | no |
| FR-003 | Never delete a tracked draft | As a reviewer who committed the feedback file, I want it left alone so that the rejection does not trade one dirty tree for another. | High | Open | [ratchet] | no — same-fixture control: the untracked twin in FR-001 is removed |
| FR-004 | Never reach outside the mission directory | As an operator, I want a `--review-feedback-file` outside `kitty-specs/<mission>/` untouched so that the fix cannot delete unrelated files. | High | Open | [ratchet] | no — same-fixture control: an inside-mission draft is removed |
| FR-005 | Retire only bytes the record already holds | As a reviewer, I want the draft kept when it changed after the record was written so that no unrecorded text is deleted. | High | Open | [build] | no |
| FR-006 | The record keeps the reviewer's text verbatim | As a reader of the record, I want the reviewer's body unchanged by this retirement so that the evidence stays intact. | High | Open | [ratchet] | no — asserts the recorded body on the same fixture FR-001 removes the source from |
| FR-007 | The review prompt states the draft lifecycle | As a reviewer, I want the prompt to describe what the rejection command actually does with my file so that I do not leave a stale copy behind. | Medium | Open | [build] | no |
| FR-008 | Announce a retirement that could not happen | As an operator, I want a warning when the draft could not be removed so that I know to commit or delete it myself. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Bounded extra cost | Retirement adds at most two git invocations and 100 ms to a rejection on a fixture repository. | Performance | Medium | Open |
| NFR-002 | Never fail a recorded rejection | A retirement error never turns an exit-0 rejection with a durable record into a non-zero exit; it is reported on stderr and the move proceeds. | Reliability | High | Open |
| NFR-003 | One owning seam | The retirement has exactly one implementation, in the module that writes the record (`review/cycle.py::create_rejected_review_cycle`); no caller re-implements it. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Do not commit the draft anywhere | The draft is retired, never committed: committing it onto a review lane re-introduces the squash-carried deletion reported in #6632's first comment. | Technical | High | Open |
| C-002 | No change to what is recorded | Retirement moves no bytes into or out of `review-cycle-N.md`; the artifact writer and its provenance guard are untouched. | Technical | High | Open |
| C-003 | Keep the existing failure contracts | The typed errors for a missing, non-file, empty or non-UTF-8 feedback file keep their current codes and wording. | Technical | High | Open |

### Key Entities

- **Review feedback draft** (`tasks/<wp-dir>/review-feedback-N.md`): the reviewer-authored file the
  review prompt advertises. Input only; no reader depends on it after the record is written.
- **Review-cycle record** (`tasks/<wp-dir>/review-cycle-N.md`): the tool-authored, committed verdict
  artifact. It carries the draft's body verbatim and is the durable evidence the loop reads.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a fixture mission, the printed rejection command followed by `move-task --to for_review` both exit 0 with no manual commit, and `git status --porcelain kitty-specs/<mission>/` is empty after the rejection — [build] · no-op passable: no
- **SC-002**: Every non-durable, tracked, out-of-mission or changed-after-read draft survives the rejection byte-identical (one assertion per case on the shared fixture) — [build] · no-op passable: no
- **SC-003**: The record still contains the reviewer's text verbatim after the draft is retired — [ratchet] · no-op passable: no
- **SC-004**: The targeted test files for the touched modules and the named architectural gates pass, with the changelog and the affected docs updated — [ratchet] · no-op passable: no
