# Mission Specification: Retrospect: one signal for documented review rejections

**Mission Branch**: `claude/issue-2267-77kxtr`
**Created**: 2026-10-01
**Status**: Draft
**Input**: GitHub issue #2267 — "retrospect: auto-classifier mislabels review-rejection --force as guard-bypass and documented rejection cycles as undocumented rework", plus the follow-up comments on the issue (kentonium3, 2026-08-21; zohar, 2026-10-01).

## Intent Summary

A reviewer sends a work package (WP) back with `spec-kitty agent tasks move-task WP## --to planned --force --review-feedback-file <path>`. The status event carries a `review_ref` pointing at the `review-cycle-N.md` artifact. That is the documented rejection path.

Today three consumers read that one event independently and disagree about it:

1. `retrospect create` files it under `not_helpful` as a `--force` override ("the runtime guard failed or the operator routed around it").
2. `retrospect create` counts the re-entry into `in_progress` that follows it as "rework not captured as a documented review rejection".
3. `retrospect create` files a rejection out of `for_review` (the reviewer never claimed into `in_review`) or out of `in_progress` as a "lane bounce outside the documented reviewer-feedback flow".
4. `consolidate`'s "Hollow reviews detected" warning keys on the raw `force_count`, which rises with every documented rejection, so it names the most-reviewed WPs.

Reproduced on main at `66e4d50c` with the in-repo mission `worktree-owned-root-3328-01KZRG01`: WP06 went through three documented rejections and was reported as 3 lane bounces, 2 force overrides and 4 implementation cycles, with no `review_loop` finding at all.

The mission gives the project one predicate for "a documented review rejection" and makes every consumer read it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A documented rejection is reported once, as a review loop (Priority: P1)

An operator runs `spec-kitty retrospect create` for a mission whose WPs went through ordinary reject → fix → approve cycles. Each documented rejection appears exactly once, as a `review_loop` finding. No `process` "force override" finding, no "lane bounce" finding and no "implementation cycles … not captured as a documented review rejection" finding is emitted for those events.

**Why this priority**: This is the defect the issue reports; three independent reproductions exist.

**Independent Test**: Generate a retrospective over an event log holding documented rejections out of `in_review`, `for_review`, `in_progress` and `approved`, and assert the finding set.

**Acceptance Scenarios**:

1. **Given** a WP rejected with `--force` from `in_review` to `planned` carrying a `review_ref`, **When** the retrospective is generated, **Then** it holds one `review_loop` finding for the WP and no `process` force-override finding.
2. **Given** a WP rejected from `for_review` to `planned` with `--force` and a `review_ref`, **When** the retrospective is generated, **Then** the rejection counts as a review loop, not as a lane bounce.
3. **Given** a WP that re-enters `in_progress` after each documented rejection, **When** the retrospective is generated, **Then** no "implementation cycles" finding is emitted for it.

---

### User Story 2 - Undocumented forcing and rework are still reported (Priority: P1)

The guard-bypass and undocumented-rework findings keep their value: they fire for `--force` transitions and `in_progress` re-entries that have no documented review feedback.

**Why this priority**: The fix must not turn the findings into no-ops (non-vacuity).

**Independent Test**: The same fixture as Story 1 plus a feedback-free `--force` rewind and a feedback-free re-entry, asserting those still produce findings.

**Acceptance Scenarios**:

1. **Given** a `--force` transition without review feedback, **When** the retrospective is generated, **Then** a `process` force-override finding is emitted that counts only the undocumented transitions.
2. **Given** a WP that re-enters `in_progress` without a preceding documented rejection, **When** the retrospective is generated, **Then** an "implementation cycles" finding is emitted.

---

### User Story 3 - The hollow-review warning does not count documented rejections (Priority: P2)

At `spec-kitty consolidate`, the hollow-review warning no longer counts `--force` transitions that are documented review rejections towards its `force_count>=2` threshold.

**Why this priority**: Same signal, same defect, raised on the issue; a second reader of the raw count would keep a parallel authority alive.

**Independent Test**: Call the hollow-review collector over a mission whose `status.json` reports `force_count=2` where both forced events are documented rejections, and where the implementer and approver are not provably distinct.

**Acceptance Scenarios**:

1. **Given** `force_count=2` where both forced events are documented rejections, **When** hollow-review warnings are collected, **Then** the WP is not warned about.
2. **Given** `force_count=2` where both forced events carry no review feedback, **When** hollow-review warnings are collected, **Then** the WP is still warned about with `force_count=2`.

### Edge Cases

- A rejection out of `approved` or `done` with feedback stays a rejection; without feedback it stays lane friction (#3687 behaviour preserved).
- A feedback-free `for_review → in_progress` rewind stays lane friction.
- Bootstrap actors (`finalize-tasks`, `bootstrap`, `migrate`) remain excluded from force and cycle counts.
- An unreadable `status.events.jsonl` at consolidate leaves the raw `force_count` in force (fail toward warning).
- A WP with a documented rejection never appears in `helped` (#3687 invariant preserved).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | One rejection predicate | As a maintainer, I want one status-owned predicate that says whether a lane event is a documented review rejection (a backward rework move carrying review feedback) so that every consumer classifies the same event the same way. | High | Open | [build] | no |
| FR-002 | Rejection from any review-adjacent lane | As an operator, I want a backward move carrying review feedback out of `for_review`, `in_review`, `in_progress`, `approved` or `done` counted as a review rejection so that a rejection the reviewer issued without claiming is not a lane bounce. | High | Open | [build] | no |
| FR-003 | Force findings exclude documented rejections | As an operator, I want the force-override finding to count only `--force` transitions that are not documented review rejections so that the standard rejection path is not reported as a guard bypass. | High | Open | [build] | no |
| FR-004 | Cycle findings exclude documented rework | As an operator, I want an `in_progress` re-entry that follows a documented rejection treated as expected rework so that the implementation-cycles finding only reports undocumented rework. | High | Open | [build] | no |
| FR-005 | Hollow-review reads the corrected signal | As an operator, I want the consolidate hollow-review warning to discount documented-rejection force transitions from `force_count` so that it stops naming the WPs with the strongest review history. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Complexity ceiling | Every changed or new function stays at cyclomatic complexity <= 15 (ruff C901). | Maintainability | High | Open |
| NFR-002 | Lint and type gates | `ruff check`, `ruff format --check` and `mypy` report zero issues on every changed file. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Lane matrix unchanged | The status lane matrix and `move-task` transition rules are not changed; refusing `approved → in_progress` (raised on the issue) is out of scope. | Technical | High | Open |
| C-002 | Record schema unchanged | The retrospective record schema and finding categories are not changed. | Technical | High | Open |
| C-003 | Red-first | Each defect lands an issue-pinned repro that is RED on the base before the fix (ADR 2026-07-17-1). | Process | High | Open |

### Key Entities

- **Documented review rejection**: a lane event that moves a WP backward into `planned`, `claimed` or `in_progress` and carries review feedback (`review_ref`, a structured changes-requested review evidence, or non-empty string evidence).
- **Force override**: an operator `--force` lane transition that is not a bootstrap event, not a no-op, and not a documented review rejection.
- **Undocumented re-entry**: an entry into `in_progress` from `planned`/`claimed`, after the first, that is not preceded by a documented review rejection since the previous entry.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Regenerating the retrospective for `worktree-owned-root-3328-01KZRG01` yields zero force-override, lane-bounce and implementation-cycle findings for the WPs whose rework is fully documented, and one `review_loop` finding per rejected WP. — [build] · no-op passable: no
- **SC-002**: A fixture with feedback-free forcing and re-entry still yields the force-override and implementation-cycle findings. — [build] · no-op passable: no
