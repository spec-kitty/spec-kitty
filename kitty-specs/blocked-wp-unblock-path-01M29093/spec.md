# Mission Specification: Blocked-WP unblock path (alloc-failure recovery)

**Mission Branch**: `fix/3937-blocked-wp-unblock`
**Created**: 2026-09-11
**Status**: Draft
**Input**: GitHub issue #3937 — "Failed implement claim leaves WP blocked with no sane unblock path" (findings F-50, F-51).

## Intent Summary *(confirmed — discovery minimized per operator instruction to run the mission end-to-end)*

- **Primary actor**: an operator or orchestrating agent driving a mission's implement→review loop through the `spec-kitty` CLI.
- **Trigger**: `spec-kitty implement WP##` fails during workspace allocation because a dependency lane (or the recorded planning commit) cannot be auto-merged — a *tooling/environment* condition, not a review outcome.
- **Desired outcome**: the work package remains in a state the operator can recover from with a single legal, honest command; the CLI tells them exactly what that command is; and no one is ever forced to fabricate a review rejection to continue.
- **Rule that must always hold**: a work package is only moved into `blocked` by a genuine domain block; a tooling failure that left the work package `planned` must leave it `planned`. Every transition refusal must name the legal target(s) for the current state, and must apply its review-feedback requirement only to review-family transitions.
- **Scope boundary**: fixes findings F-50 and F-51 for issue #3937. *(Amended 2026-09-14: only F-50 ships. F-51 was cut before merge — its implementation removed a force-proof authorization gate, letting a terminal work package be resurrected to `planned`. See "Post-review descope" in [tasks.md](./tasks.md) for the measured outcomes and the design constraint for a future attempt. #3937 stays open for F-51.)* Deferred with follow-up: a first-class cause-tagged recovery driver / `blocked → in_progress` re-entry (issue #1711 class) and the resume-claim/prompt-regeneration defect (issue #3938, F-52).

**Assumptions** (recorded, not deferred decisions):
- The persisted lane worktree after a self-cleaning allocation failure is the allocator's reentrancy vehicle, not stranded state (verified: the allocator aborts and hard-resets before raising, and does not write `lanes.json`). No disk cleanup is added by this mission.
- The manufactured `blocked` state is not load-bearing for dependency gating (dependency readiness already treats `blocked` and `planned` identically), so ceasing to emit it changes no dependent's readiness.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A tooling allocation failure leaves the work package recoverable (Priority: P1)

An operator runs `spec-kitty implement WP04`. Allocation fails with "cannot auto-merge dependency lane … the merge conflicts" because a dependency lane genuinely conflicts. Today the work package is silently demoted to `blocked`, a state it cannot legally leave, and the printed guidance ("re-run the implement command") does not work. The operator wants the work package left where it was (`planned`) and to be told the real next step to resolve the conflict.

**Why this priority**: This is the core defect (F-50). Without it, a single tooling hiccup permanently wedges a work package and forces a fabricated review rejection to escape — a governance-integrity loss.

**Independent Test**: Drive `implement` against a WP whose dependency lane conflicts; assert the work package's lane is unchanged (`planned`, no `planned → blocked` event in the status log) and the printed message contains the allocator's actionable resolution step.

**Acceptance Scenarios**:

1. **Given** a work package in `planned` whose dependency lane cannot be auto-merged, **When** `spec-kitty implement` is run and allocation fails, **Then** the work package remains `planned` (no `blocked` transition is emitted) and the operator sees the conflict's actionable resolution guidance (not a bare "re-run").
2. **Given** the same failure has occurred, **When** the operator resolves the underlying conflict and re-runs `spec-kitty implement`, **Then** the command proceeds without first requiring any unblock step or review-feedback artifact.
3. **Given** a planning-commit merge conflict (the second allocation-failure path), **When** allocation fails, **Then** the work package likewise remains `planned` with actionable guidance and no manufactured `blocked` transition.

---

### User Story 2 - A transition refusal states the legal recovery instead of demanding a fake review (Priority: P1)

An operator holding a work package that is genuinely `blocked` (or reacting to any illegal transition) runs `spec-kitty ... move-task WP04 --to planned`. Today they are first told they must supply `--review-feedback-file` ("cannot be bypassed with --force"); only after fabricating one are they told the transition was illegal all along. They want a single, honest refusal that names the legal targets and does not demand a fake review artifact for a non-review transition.

**Why this priority**: This is F-51. The two-stage refusal both wastes cycles and coerces a false review record; the fix restores an honest, self-documenting error.

**Independent Test**: Request an illegal transition out of `blocked` and assert the refusal identifies it as an illegal transition (naming the legal targets) rather than demanding a review-feedback file; assert that supplying a review-feedback file cannot change that verdict.

**Acceptance Scenarios**:

1. **Given** a work package in `blocked`, **When** the operator requests `move-task --to planned` with no review feedback, **Then** the refusal states the transition is illegal and enumerates the legal targets for `blocked`, and does **not** demand a `--review-feedback-file`.
2. **Given** the same request, **When** the operator supplies a `--review-feedback-file`, **Then** the verdict is unchanged (still refused as an illegal transition) — a review artifact cannot launder a structurally illegal transition.
3. **Given** a legitimate review-family rollback (e.g. a work package in `in_review` moving to `planned`), **When** `move-task --to planned` is requested without feedback, **Then** the review-feedback requirement still applies exactly as before (no regression to the honest path).
4. **Given** an attempt to start implementation on a `blocked` work package, **When** the CLI refuses, **Then** the "cannot start implementation" message names the legal recovery command for the current state.

### Edge Cases

- A work package that was **already** `in_progress`/`claimed` when a *later* operation fails must not be dragged back to `planned` by this change — only the still-`planned` allocation-failure path is affected.
- The refusal-message enumeration must be sourced from the authoritative per-state allowed-targets so it cannot drift from the real transition matrix.
- The change must not alter the machine-readable illegal-transition string consumed by the FSM parity fixtures; operator-facing enumeration is surfaced only on the CLI/emit refusal path.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Tooling allocation failure preserves `planned` | As an operator, I want a workspace-allocation failure to leave my work package in `planned` (not manufacture a `blocked` state) so that a tooling hiccup never wedges the work package. | High | Open |
| FR-002 | Actionable failure guidance | As an operator, I want the allocation-failure message to state the real resolution step (the conflict's next step) so that I can fix the cause instead of looping on a useless "re-run". | High | Open |
| FR-003 | Both allocation-conflict paths covered | As an operator, I want both the dependency-lane and planning-commit conflict paths to behave identically (stay `planned`, actionable guidance) so that recovery is uniform. | High | Open |
| FR-004 | Illegal transition names legal targets | As an operator, I want an illegal transition request to be refused with the legal targets for the current state so that I know the one right next move. | High | Open |
| FR-005 | Review-feedback demanded only for review-family sources | As an operator, I want the `--review-feedback-file` requirement to apply only when the source state is a review-family lane so that a non-review transition (e.g. out of `blocked`) is never gated on a fabricated review artifact. | High | Open |
| FR-006 | Review artifact cannot launder an illegal transition | As an operator, I want supplying a review-feedback file to be unable to change the verdict on a structurally illegal transition so that no fake finding can force an illegal move. | Medium | Open |
| FR-007 | Start-implementation refusal names recovery | As an operator, I want the "cannot start implementation" refusal on a `blocked` work package to name the legal recovery command so that I am never left guessing. | Medium | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Behavior pinned by state, not prose | Every acceptance test asserts observable state (work-package lane / emitted transition events / refusal identity), not merely message substrings; a cosmetic message change alone must not satisfy any test. | Reliability | High | Open |
| NFR-002 | No FSM-core fixture churn | The change must not modify the machine-readable illegal-transition string asserted by the FSM parity fixtures (`fsm_parity_baseline.jsonl`); zero rows of that baseline change. | Reliability | High | Open |
| NFR-003 | Type + lint clean | New/changed code passes `mypy --strict` and `ruff` with zero new issues and no new suppressions. | Maintainability | High | Open |
| NFR-004 | Parity with existing correct path | CLI allocation-failure behavior aligns with the already-correct orchestrator-api path, which never emits `blocked`. | Consistency | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No R3 recovery driver | Do not add a `BLOCKED` branch / `blocked → in_progress` driver to the start-implementation path; that is the issue #1711 class (skips the claimed slot) and is out of scope. | Technical | High | Open |
| C-002 | No guard reordering that shifts persist-signal prefixes | F-051 must be fixed by a source-lane-scoped early-return in the review-feedback guard, not by reordering the guard tuple in a way that changes persist-signal semantics. | Technical | High | Open |
| C-003 | Deferred follow-up tracked | Issue #3938 (F-52 resume-claim + prompt regeneration) is co-sequenced and deferred-with-followup, not folded into this mission. | Process | Medium | Open |
| C-004 | Terminology canon | All new CLI flags, messages, and docs use canonical `Mission`/`--mission` terminology; no `feature*` aliases introduced. | Business | Medium | Open |

### Key Entities

- **Work Package (WP)**: the unit of mission work whose lifecycle lane (`planned`, `claimed`, `in_progress`, `blocked`, …) is governed by the transition matrix.
- **Lane transition**: a typed move between lifecycle lanes, refused unless legal for the source state; some review-family transitions additionally require a review-feedback artifact.
- **Allocation failure**: a tooling/environment condition (dependency-lane or planning-commit merge conflict) raised while preparing a work package's execution workspace.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After a workspace-allocation failure, 100% of affected work packages remain in `planned` with zero manufactured `blocked` transitions, and a plain re-run (after the operator resolves the cause) needs zero intermediate unblock steps.
- **SC-002**: Zero fabricated review-feedback artifacts are required to recover from a tooling-caused failure (down from one per incident today).
- **SC-003**: 100% of illegal-transition refusals name the legal target set for the current state in a single message (no two-stage refusal).
- **SC-004**: Zero rows of the FSM parity baseline change, and the required test surface (status transitions, allocation-failure emit, move-task guards) passes with the new behavior.
