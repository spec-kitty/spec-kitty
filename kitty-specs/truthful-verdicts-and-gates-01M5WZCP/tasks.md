# Tasks: Truthful verdicts and gates

**Mission**: `truthful-verdicts-and-gates-01M5WZCP` · **Spec**: [spec.md](spec.md) · **Plan**: [plan.md](plan.md)

Three independent work packages, one per defect group and one pull request each. None depends on another; all three can run in parallel lanes.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Red-first tests: approval with feedback file keeps its content; multi-word reviewer replay command | WP01 | |
| T002 | Thread a feedback-file body preamble through the review-cycle writer | WP01 | |
| T003 | Approval writer uses the feedback file (and writes a cycle on re-approval with a file) | WP01 | |
| T004 | Refuse a supplied feedback file the approval cannot record (damaged verdict slot) | WP01 | |
| T005 | Quote the approval replay command with `shlex.join` | WP01 | |
| T006 | Red-first tests: in-mission row for an uncited issue; zero gating refs with a matrix; zero refs without one | WP02 | [P] |
| T007 | At done, collect in-mission rows over every matrix row | WP02 | [P] |
| T008 | Blocker evaluates an existing matrix at done when there are no gating references | WP02 | [P] |
| T009 | Consolidation gate's zero-reference arm reads the matrix without failing on an absent one; honest PASS text | WP02 | [P] |
| T010 | Red-first CLI tests: lone named ignored file vs mixed call; non-ASCII directory expansion | WP03 | [P] |
| T011 | Candidate pre-check counts explicitly named ignored files | WP03 | [P] |
| T012 | Verify unchanged-file and ignored-directory behaviour stays as documented | WP03 | [P] |

## Work Package WP01 — Approval record keeps the review and a replayable command (P1)

**Prompt**: [tasks/WP01-approval-record-feedback-and-replay.md](tasks/WP01-approval-record-feedback-and-replay.md)
**Goal**: FR-001..FR-006 (#6652, #6654). **Independent test**: approve with a feedback file and a multi-word reviewer; read the record.
**Dependencies**: none.

T001 Red-first tests (WP01)
T002 Body preamble in the review-cycle writer (WP01)
T003 Approval writer uses the feedback file (WP01)
T004 Refuse an unrecordable feedback file (WP01)
T005 shlex-quoted replay command (WP01)

**Risks**: the provenance guard must keep refusing a prior review-cycle artifact; the synthesized no-file body stays on `body=` (M1).

## Work Package WP02 — Terminality gate evaluates every row it reports on (P1)

**Prompt**: [tasks/WP02-terminality-gate-all-rows.md](tasks/WP02-terminality-gate-all-rows.md)
**Goal**: FR-007..FR-010 (#6653). **Independent test**: an in-mission row for an uncited issue fails the done-gate and the consolidation gate.
**Dependencies**: none.

T006 Red-first tests (WP02)
T007 All-rows in-mission at done (WP02)
T008 Zero-reference evaluation in the blocker (WP02)
T009 Zero-reference arm in the consolidation gate (WP02)

**Risks**: #5222 F1 — a coordination Mission with no matrix must not fail on the coordination probe.

## Work Package WP03 — safe-commit pre-check sees what the helper stages (P2)

**Prompt**: [tasks/WP03-safe-commit-ignored-file.md](tasks/WP03-safe-commit-ignored-file.md)
**Goal**: FR-011, FR-012 (#6649, #5393). **Independent test**: a lone named ignored file is committed like the same file in a mixed call.
**Dependencies**: none.

T010 Red-first CLI tests (WP03)
T011 Count named ignored files as candidates (WP03)
T012 Verify unchanged and directory behaviour (WP03)

**Risks**: none beyond keeping directory expansion non-ignored only.
