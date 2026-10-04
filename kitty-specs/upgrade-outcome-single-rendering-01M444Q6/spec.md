# Mission Specification: Upgrade reports one outcome

**Mission Branch**: `issue-4925-upgrade-outcome-single-rendering`
**Created**: 2026-10-04
**Status**: Draft
**Input**: GitHub issue #4925 (primary) and the misreport slice of #4893, with operator steer from the rc6 kickoff: one exit-status authority for `upgrade`, derived from a structured outcome, with the final line and the exit code produced from the same value.

## Intent Summary

- **Actor**: an operator, or automation, running `spec-kitty upgrade` on a project.
- **Trigger**: the upgrade finishes, with or without migrations to apply.
- **Outcome wanted**: the closing line, the machine-readable status and the exit code always describe the same result. A run never says it succeeded while exiting as a failure, and a failing run always says why.
- **Rule that must always hold**: every upgrade run has exactly one outcome, and everything the command reports about the run is derived from it.
- **Discovery**: minimised at the operator's instruction. The defect was reproduced and traced by a grounding squad on `main` at `9adc68803f` before this spec was written (see Grounding Evidence).

## Background

On a project that is already up to date but has unresolved tool-surface drift (for example a hand-edited agent-profile projection), `spec-kitty upgrade --yes` prints only:

```text
Current version: 4.0.0rc6
Target version:  4.0.0rc6

Project is already up to date!
```

and exits 1. The same run with `--json` reports `status: failed` and the error `Unresolved tool-surface drift in N file(s); run 'spec-kitty doctor tool-surfaces' to review.` The same happens without `--yes`.

The exit code is already decided in one place. The messages are not: the list of errors is assembled separately by each presentation path, and the path used when no migrations are pending prints its success line unconditionally and never asks for the drift error. A single flag also stands for three different conditions (unresolved drift, a repair that could not be applied, an incomplete preview), so a repair failure is worded as `Unresolved tool-surface drift in 0 file(s)`.

## Domain Language

| Term | Meaning | Avoid |
|------|---------|-------|
| **Upgrade outcome** | The single result of one upgrade run: its kind, its reason when it is not a success, and the ordered messages that explain it. | "result" for the same thing in user-facing text |
| **Outcome kind** | One of: **applied** (migrations were applied, nothing unresolved), **no-op** (no migration was needed and nothing is unresolved; the run may still have refreshed supporting files), **drift-unresolved** (the only thing outstanding is tool-surface drift that was left alone), **failed** (something the upgrade attempted did not complete). When several conditions hold, failed takes precedence over drift-unresolved, and all reasons are still reported. | |
| **Tool-surface drift** | A managed file that differs from the recorded managed content and needs the operator's consent before it is overwritten. | "conflict" |
| **Closing line** | The last headline a text-mode run prints to summarise the run. | "banner" |
| **No-migrations path** | A run with no applicable migrations. | "no-op path" (a no-migrations run is not necessarily a no-op outcome) |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A run with unresolved drift says so (Priority: P1)

An operator runs `spec-kitty upgrade --yes` on an up-to-date project in which one managed agent-profile file was edited by hand. The command tells them the project has unresolved tool-surface drift, how many files are affected and how to review them, and exits non-zero. It does not tell them the project is up to date.

**Why this priority**: this is the reported defect. Today the operator gets a success message and a failure exit code, with nothing to act on.

**Independent Test**: create a converged project, edit one managed surface, run the upgrade in text mode and check the output and the exit code together.

**Acceptance Scenarios**:

1. **Given** an up-to-date project with one drifted managed file, **When** the operator runs `upgrade --yes` in text mode, **Then** the output names the drift with the count `1` and the review command, the output does not contain `already up to date`, and the exit code is non-zero.
2. **Given** the same project, **When** the operator runs `upgrade` without `--yes`, **Then** the result is the same as scenario 1.
3. **Given** the same project, **When** the operator runs `upgrade --yes --json`, **Then** `status` is `failed`, `success` is false, the errors list carries the same drift message as text mode, and the exit code equals the text-mode exit code.
4. **Given** the drifted file is restored to its managed content, **When** the operator runs `upgrade --yes`, **Then** the output is `Project is already up to date!` and the exit code is 0.

---

### User Story 2 - Automation can trust the exit code (Priority: P1)

A CI job runs `spec-kitty upgrade --yes` and gates on the exit code. Exit 0 means the project is converged; a non-zero exit always comes with a stated reason in the same output, in both text and JSON mode.

**Why this priority**: an exit code that disagrees with the message makes the command unusable in automation, which is the consequence the issue reports.

**Independent Test**: drive each outcome kind on both the migrations path and the no-migrations path, in text and JSON, and check the closing line, the JSON status and the exit code against one expected row per combination.

**Acceptance Scenarios**:

1. **Given** any upgrade run that exits 0, **When** its output is inspected, **Then** the closing line is a success line and JSON `status` is not `failed`.
2. **Given** any upgrade run that exits non-zero after reaching the end of the upgrade, **When** its output is inspected, **Then** no success closing line is printed, at least one error line states the reason, and JSON `status` is `failed`.
3. **Given** an up-to-date project where a post-upgrade step fails (an activation or preflight error, a repair that could not be applied, a worktree stamp failure, a failed commit recovery), **When** the upgrade runs in text mode, **Then** it does not print `already up to date` and it prints the failure reason.

---

### User Story 3 - A repair failure is not called drift (Priority: P2)

An operator's upgrade attempts a tool-surface repair that cannot be applied because the inputs changed while the upgrade was running. The command reports that reason. It does not report `Unresolved tool-surface drift in 0 file(s)`.

**Why this priority**: this is the misreport slice of #4893. It sends the operator to review drift that does not exist.

**Independent Test**: force a repair to fail its precondition check with no drifted files, and check that the message names the repair failure and that no message mentions drift in zero files.

**Acceptance Scenarios**:

1. **Given** a run where a repair could not be applied and no file is drifted, **When** the upgrade finishes, **Then** the outcome kind is failed, the message names the repair failure, and no output in either mode contains `drift in 0 file(s)`.
2. **Given** a run with both a failed repair and two drifted files, **When** the upgrade finishes, **Then** both reasons are reported, the drift count is `2`, and the exit code is non-zero.

---

### Edge Cases

- A run with drift and pending migrations: migrations apply, the drift is reported, the closing line is a failure line, exit is non-zero (current behaviour, must stay).
- A `--dry-run` preview that lists files "requiring separate consent": the preview keeps exiting 0 and is not turned into a failure by this mission. An incomplete preview keeps exiting 1; it is a failed outcome with its own reason, it prints no success line (today it prints `Project is already up to date!` on the no-migrations path), and its notice is printed once, not twice. The command help text is corrected to say so.
- A run where files need manual review but nothing failed is a success outcome; the manual-review list is still shown.
- The optional mission-state repair fails unexpectedly: the exit code is unchanged, and the failure is shown as a warning instead of being dropped.
- An operator declines the optional mission-state repair: this never changes the exit code (existing rule, unchanged).
- A drifted file outside the project (user-global managed skills) counts toward the drift count exactly as today. Whether it should be classified as drift is #702, out of scope.
- The drift message points the operator at `spec-kitty doctor tool-surfaces` to review. It must not recommend the `--fix` flag, which overwrites the edit (#5677).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | One outcome per run | As an operator, I want every upgrade run that reaches the end of the upgrade to have exactly one outcome with a kind (applied, no-op, drift-unresolved, failed), so that there is one answer to "what happened". | High | Open | [build] | no |
| FR-002 | Outcome owns its messages | As an operator, I want the ordered list of error and warning messages to belong to the outcome, so that every presentation of the run shows the same reasons. | High | Open | [build] | no |
| FR-003 | Closing line, status and exit code derive from the outcome | As automation, I want the text closing line, the JSON `status` / `success` / `errors` and the exit code to be produced from the outcome on both the migrations path and the no-migrations path, so that they cannot disagree. | High | Open | [build] | no |
| FR-004 | Drift is stated in text mode | As an operator, I want a no-migrations run with unresolved drift to print the drift count and how to review it, and to exit non-zero, so that I know why the run failed. | High | Open | [build] | no |
| FR-005 | No success line on a non-zero exit | As an operator, I want `already up to date` (or any other success closing line) never printed when the exit code is non-zero, so that the output is not contradictory. | High | Open | [build] | no |
| FR-006 | Clean no-op stays a success | As an operator, I want a run with nothing to do and nothing unresolved to print `Project is already up to date!` and exit 0, so that converged projects pass. | High | Open | [ratchet] | yes — paired with FR-004 on the same project fixture, before and after the drift edit |
| FR-007 | Applied upgrade stays a success | As an operator, I want a run that applied migrations with nothing unresolved to keep its success line and exit 0. | High | Open | [ratchet] | yes — paired with the migrations-plus-drift row of the FR-011 matrix on the same fixture |
| FR-008 | Repair failure has its own reason | As an operator, I want a repair that could not be applied reported as a repair failure, distinct from drift, and always with a stated reason (naming the affected surface owner and what happened when no more specific diagnostic exists), so that I am not sent to review drift that does not exist and never get a non-zero exit with nothing printed. | Medium | Open | [build] | no |
| FR-009 | Drift count is never zero in a drift message | As an operator, I want a drift message emitted only when at least one file is drifted. | Medium | Open | [build] | no |
| FR-010 | Review advice is safe | As an operator, I want the drift message to point me at reviewing the drift and never to recommend an option that overwrites my edits. | Medium | Open | [build] | no |
| FR-011 | Outcome matrix is pinned | As a maintainer, I want one test matrix, driven through the command entry point, covering outcome kind × text/JSON × migrations/no-migrations, plus the dry-run complete and dry-run incomplete rows, that asserts the reported outcome kind, closing line, JSON status and exit code together, so that a future change cannot split them again. | High | Open | [build] | no |
| FR-012 | Presentation cannot bypass the outcome | As a maintainer, I want a structural guard that fails when (a) a closing-line text exists anywhere other than the outcome, (b) a presentation path receives or assembles its own error list or success flag instead of asking the outcome, or (c) the exit code is computed from anything but the outcome kind, so that the defect class stays closed. | Medium | Open | [build] | no |
| FR-013 | Existing exit-only tests assert the message | As a maintainer, I want the existing tests that check only a non-zero exit on drift to also check what the operator is told. | Medium | Open | [build] | no |
| FR-014 | Help text matches dry-run behaviour | As an operator, I want the `upgrade` help text, and the generated CLI reference and completion data that mirror it, to describe the dry-run exit codes as they are. | Low | Open | [build] | no |
| FR-015 | Contract is recorded | As a maintainer, I want the upgrade outcome and exit-code contract recorded as an architecture decision and in the changelog, replacing the "known limitation" note about #4925. | Medium | Open | [build] | no |
| FR-016 | Unreachable presentation path is settled | As a maintainer, I want the older surface-repair presentation path, confirmed unreachable by the post-spec review, removed together with the six inert test patches that still target it, so that there is one path to keep honest. | Low | Open | [build] | no |

| FR-017 | Kind is machine-readable | As automation, I want the JSON output to state the outcome kind and the reasons, so that I can tell unresolved drift from a failure without parsing messages. | Medium | Open | [build] | no |
| FR-018 | Optional repair failure is visible | As an operator, I want an unexpected failure of the optional mission-state repair shown as a warning, with the exit code unchanged, so that it is not silently dropped. | Low | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Text and JSON parity | For 100% of the outcome-matrix rows, the text-mode exit code equals the JSON-mode exit code and the text error lines contain every message in the JSON `errors` list. | Reliability | High | Open |
| NFR-002 | No JSON contract break | 0 keys removed or renamed in the `upgrade --json` payload; existing values for `status` and `success` keep their current vocabulary. New keys may be added. | Compatibility | High | Open |
| NFR-003 | Exit codes unchanged for existing passing cases | 0 changes to the exit code of any scenario already pinned by an existing upgrade test, other than tests this mission strengthens. | Compatibility | High | Open |
| NFR-004 | New code is covered | At least 90% line coverage on changed lines, and cyclomatic complexity of every touched function at or below 15. | Maintainability | Medium | Open |
| NFR-005 | Guard is non-vacuous | The FR-012 guard starts with an empty allowlist and has a self-mutation check proving it fails when a presentation path bypasses the outcome. | Maintainability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Extend the existing authority | The outcome that already decides the exit code is extended; no second outcome or exit-status authority is introduced. | Technical | High | Open |
| C-002 | Drift stays a non-zero exit | Unresolved drift keeps a non-zero exit code. This is the contract pinned by earlier missions and tests. Changing it to a zero exit with a warning is an operator decision recorded under Open Decisions and is not made here. | Business | High | Open |
| C-003 | Stay out of the sibling mission's files | The upgrade runner and the per-worktree metadata writes (sibling mission for #5457) are not modified; the worktree failure list keeps its current shape. | Technical | High | Open |
| C-004 | Red-first | Each defect lands a failing reproduction through the existing command entry point before the fix. | Process | High | Open |
| C-005 | No priority or version changes | The mission does not set or raise issue priorities and assigns no version numbers. | Process | Medium | Open |
| C-006 | Planner and compatibility exits untouched | The exit codes and JSON vocabulary of the planning and compatibility paths (`--cli`, `--plan-json`, `--json` with `--project` or `--dry-run`, agent-check flags) are not changed. | Technical | Medium | Open |

### Key Entities

- **Upgrade outcome**: kind, reason(s) when not a success, ordered messages, the drifted paths and their count, the exit code derived from the kind.
- **Reason**: why a run is not a success: unresolved drift, repair not applied, post-upgrade step failed, migration failed, worktree stamp failed.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On an up-to-date project with one drifted managed file, a text-mode upgrade prints the drift count and review command, prints no success line, and exits non-zero, in 100% of runs. — [build] · no-op passable: no
- **SC-002**: Across every row of the outcome matrix, the closing line, the machine-readable status and the exit code agree; 0 rows disagree. — [build] · no-op passable: no
- **SC-003**: No upgrade run in either mode emits a drift message with a count of zero. — [build] · no-op passable: no
- **SC-004**: A converged project with no drift exits 0 with `Project is already up to date!`, unchanged from today. — [ratchet] · no-op passable: yes — same fixture as SC-001 before the drift edit
- **SC-005**: #4925 can be closed by the pull request; #4893 stays open with only its ordering defect remaining. — [build] · no-op passable: no

## Open Decisions

- **Exit code on unresolved drift (operator)**. This mission keeps the non-zero exit and makes text mode state the reason (C-002). The alternative, exit 0 with a warning on a no-migrations run, would reverse a contract pinned by FR-006 of `agent-profile-projection-plugin-production-01KV3NGS#FR-006`, by #3392 and by #5575. One cost of keeping it: until #702 is fixed, untouched generated files can be classified as drift, so an unattended upgrade can exit non-zero with no real edit. The architecture decision record (FR-015) states the contract either way.

## Assumptions

- The grounding trace on `9adc68803f` holds for the branch base; line references are re-verified at plan time.
- The older surface-repair presentation path is unreachable in production (inference from code reading); FR-016 verifies before removing anything.
- `upgrade --project --yes --json` returning the compatibility planner's result without running the upgrade is existing behaviour and stays (C-006); it is recorded as a follow-up.

## Scope

**In scope**: the upgrade outcome, the two text presentation paths and the JSON presentation of a completed upgrade, the tests named in FR-011 to FR-013, the help text, the changelog and one architecture decision record.

**Out of scope** (context only):

- The ordering defect in #4893 (repair inputs fingerprinted before the upgrade writes project configuration). The issue stays open.
- Drift classification: see #702 and the children of epic #4807.
- `doctor tool-surfaces --fix` overwriting a user edit: see #5677.
- Per-worktree metadata writes during upgrade: see #5457 (sibling mission).
- Follow-up: the planning and compatibility exit vocabulary (C-006), and #5470 (the inverse class).
- Context: parent epic #3347; earlier fixes #3392, #4775, #5574, #5575; PR #5694 is open on neighbouring files.

## Grounding Evidence

- Reproduced on `main` `9adc68803f` (CLI 4.0.0rc6, Linux, isolated home): text mode silent with exit 1; JSON `status: failed` with the drift error; identical without `--yes`.
- The exit code is derived once, by the outcome. The error list is assembled outside it, and the no-migrations text presentation never requests it and prints its success line unconditionally.
- One flag carries three conditions, which produces `drift in 0 file(s)` on a repair failure.
- Existing tests pin a non-zero exit on drift in text mode without asserting any message; one records the missing message as a test-harness limit.
