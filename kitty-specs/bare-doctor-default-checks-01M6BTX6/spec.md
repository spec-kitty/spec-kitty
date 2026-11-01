# Mission Specification: Bare `spec-kitty doctor` runs a default check set

**Mission Branch**: `issue-6969-bare-doctor-default-checks`
**Created**: 2026-11-01
**Status**: Draft
**Input**: GitHub issue #6969 — "Bare `spec-kitty doctor` runs no diagnostic and exits 2"

**Guidance recorded from the issue**: bare `doctor` must run a sensible default set of
fast, read-only, project-level checks (the issue names `command-files`, `state-roots`,
`ops` and "topology/identity where cheap"), print a summary, name the subcommand behind
each finding, and exit 0 when healthy and non-zero only on a real finding. An exit-code
test pins the behaviour, and the help text and the setup-doctor skill/docs must match.

## Context

`spec-kitty doctor` is the natural first command a person, a skill or an agent runs to
check an install. Since #4678 the bare group deliberately runs nothing: it prints the
help and exits 2 (usage error) so the output can never be mistaken for a passing check.
That reasoning was sound (an empty run must not read as "healthy") but the remedy is
wrong: "Run `spec-kitty doctor`" is used by skills, prompts and humans as the check
itself, and exit 2 reads as a failed check or a usage error to any wrapper. Issue #6969
is the maintainer's decision to replace the refusal with an actual default run.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Bare `doctor` diagnoses the project (Priority: P1)

A developer, skill or agent runs `spec-kitty doctor` with no subcommand inside a
spec-kitty project. A default set of fast, read-only, project-level checks runs, one
line comes out per check, and the exit code says whether anything was found.

**Why this priority**: This is the whole defect. Every other story refines its output
or its documentation.

**Independent Test**: Run `spec-kitty doctor` in a healthy fixture project and assert
exit 0 plus one summary line per default check; give one checked surface a real
finding and assert a non-zero exit that names the offending subcommand.

**Acceptance Scenarios**:

1. **Given** a healthy spec-kitty project and **When** `spec-kitty doctor` runs, **Then** it executes the default check set, prints a per-check summary naming each subcommand, and exits 0.
2. **Given** a project with a real finding in one default check and **When** `spec-kitty doctor` runs, **Then** it prints that finding with the subcommand that will show the full report, and exits 1.

---

### User Story 2 - Default checks are read-only and cheap (Priority: P2)

The default set never mutates state and never runs a heavy audit: an operator can run
it any time, including inside automation, without a `--fix` risk or a multi-second wait.

**Why this priority**: The default set runs on every bare invocation, so a mutating or
heavy member would make the command unsafe or slow to recommend.

**Independent Test**: Assert every default check is built on a read-only primitive (no
`fix`/`repair`/`close-stale` path) and that the set is a fixed, documented list.

**Acceptance Scenarios**:

1. **Given** a project with fixable defects, **When** bare `doctor` runs, **Then** no file, worktree, index or Op record is modified and the exit code reports the finding.
2. **Given** the default set, **When** a check raises unexpectedly, **Then** that check is reported as failed, the remaining checks still run, and the exit code is non-zero.

---

### User Story 3 - The documented story matches the behaviour (Priority: P3)

The `doctor` help text, the changelog and the setup-doctor skill describe the default
run, so a governed agent reading the docs knows that bare `doctor` is a real check.

**Why this priority**: The issue calls out docs and help drift explicitly; a behaviour
change whose docs still say "needs a subcommand" recreates the confusion.

**Independent Test**: Read the help output, the changelog `[Unreleased]` entry and the
setup-doctor skill and confirm each describes the default run.

**Acceptance Scenarios**:

1. **Given** `spec-kitty doctor --help`, **When** read, **Then** it states that a bare invocation runs the default check set and names the exit-code contract.
2. **Given** the changelog and the setup-doctor skill, **When** read, **Then** both describe bare `doctor` as a check, not as a usage error.

---

### Edge Cases

- **Not in a spec-kitty project**: bare `doctor` reports the standard not-in-project error and exits 1 (never 2, never 0), matching every other project-root doctor check.
- **A check raises**: the exception is caught, reported as a check failure with its message, and the remaining checks still run; exit code is non-zero.
- **`--help` / `-h`**: still prints help and exits 0; help routing must not swallow the default run or vice versa.
- **A real subcommand**: `spec-kitty doctor <subcommand>` keeps its exact current behaviour and exit codes; the default run never intercepts it.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Bare doctor runs the default check set | As a developer, I want bare `spec-kitty doctor` to actually diagnose my project so that the most natural command is also a real check. | High | Open | [build] | no — the exit-2 pre-state fails the pinned exit-code test |
| FR-002 | Default set is fast, read-only, project-level | As an operator, I want the default run to touch nothing and finish quickly so that I can run it inside automation. | High | Open | [build] | no — a mutating default is detectable on the fixture |
| FR-003 | Summary names the subcommand for each check and finding | As a user, I want each line to name the subcommand that produces the full report so that I can drill down without guessing. | High | Open | [build] | no — each finding line is asserted to carry its subcommand |
| FR-004 | Exit code reflects health, not invocation shape | As automation, I want 0 when the default checks are healthy and 1 when a check reports a finding so that a wrapper cannot misread a usage error. | High | Open | [build] | no — the pinned test asserts 0/1, and 2 fails it |
| FR-005 | A failing check never aborts the run | As a user, I want one broken check to still report the others so that a single defect does not hide the rest. | Medium | Open | [build] | no — an injected exception is asserted to leave the other checks reported |
| FR-006 | Help text, changelog and setup-doctor docs describe the default run | As a governed agent, I want the documented story to match the behaviour so that I do not misread a real check. | Medium | Open | [build] | no — the docs are asserted to describe the default run |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Default run stays off the slow path | The default check set is at most three checks, all backed by in-memory or single-directory reads; the pinned test runs the bare invocation in-process well inside the fast-suite budget. | Performance | High | Open |
| NFR-002 | Default run mutates nothing | No default check can write, repair, sweep or delete: the test asserts the fixture project's content is unchanged after a bare run. | Reliability | High | Open |
| NFR-003 | Existing subcommand contracts are preserved | Every existing `doctor <subcommand>` keeps its current output shape and exit codes; the only changed surface is the bare invocation and the group help string. | Compatibility | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | New logic lives in a sibling module | `cli/commands/doctor.py` is an orchestration shim (#2059); the default-run aggregation lives in a `_*_doctor` sibling, and the `@app.callback` shell only delegates. | Technical | High | Open |
| C-002 | Single canonical console | All output goes through the shared `console` in `_doctor_shared` so `--json` stdout cleanliness and the doctrine snapshots are unaffected. | Technical | Medium | Open |
| C-003 | No new mutating flags on the group | The default run adds no repair/mutating flag; subcommands keep owning those. | Technical | Medium | Open |

### Key Entities

- **Default check**: a named, read-only diagnostic with its owning subcommand, a one-line description, and a primitive that returns its findings.
- **Default run report**: the ordered per-check results (healthy / findings / error) and the aggregate exit code.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `spec-kitty doctor` on a healthy fixture project exits 0 and prints one line per default check — [build] · no-op passable: no
- **SC-002**: `spec-kitty doctor` on a project with a planted finding exits 1 and names the owning subcommand — [build] · no-op passable: no
- **SC-003**: Nothing under the fixture project is modified by a bare run — [build] · no-op passable: no
- **SC-004**: `doctor --help`, the `[Unreleased]` changelog entry and the setup-doctor skill all describe the default run — [build] · no-op passable: no
