# Mission Specification: Charter reported paths are POSIX on every OS

**Mission Branch**: `issue-7044-charter-reported-paths-posix`
**Created**: 2026-11-02
**Status**: Draft
**Input**: Issue #7044 — `charter generate/interview --json` still report backslash paths on Windows. Follow-up to #6277, which fixed the same defect in `charter synthesize --json` by giving the repository one seam, `kernel.charter_pack_paths.repo_relative_posix()`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A machine consumer of the charter envelopes reads one path spelling (Priority: P1)

A tool (CI job, editor integration, script) runs `spec-kitty charter generate --json` or
`spec-kitty charter interview --json` and uses the reported path as a stable identifier: it
writes it to a cache key, compares it against a configured value, or checks it out of the
envelope to open the file. On Windows those envelopes spell the path
`.kittify\charter\charter.md`; on Linux and macOS the same envelope spells
`.kittify/charter/charter.md`. A consumer then needs a platform branch of its own to read the
same envelope.

**Why this priority**: The envelope is a contract consumed by machines, not a human at a
terminal; a per-OS spelling is a contract that differs per platform, which is exactly the
class of defect #6277 fixed for `charter synthesize --json`.

**Independent Test**: Run both commands with `--json` in a scratch repository under the
Windows path-rendering simulation (see below) and assert the reported string contains no
backslash and equals the `.kittify/...` value Linux reports.

**Acceptance Scenarios**:

1. **Given** a scratch repository with a generated interview, **When** `spec-kitty charter generate --json` runs while `Path.relative_to` renders Windows separators, **Then** `charter_path` is `.kittify/charter/charter.md` and contains no `\`.
2. **Given** a scratch repository, **When** `spec-kitty charter interview --defaults --json` runs under the same simulation, **Then** `interview_path` is `.kittify/charter/interview/answers.yaml` and contains no `\`.
3. **Given** the same fixtures on a POSIX host without the simulation, **When** both commands run, **Then** the reported strings are byte-identical to the simulated-Windows run (no platform-dependent spelling remains).

### User Story 2 - The human-readable charter output spells one path (Priority: P2)

An operator runs a charter verb without `--json` and copies the path it prints into a
follow-up command, or reads it in a support thread next to a Linux user's output. The text
lines (`Charter: …`, `Interview file: …`, and the missing/malformed-interview error message)
and `_display_path()`'s callers (the `charter status` family) spell repository-relative paths
with the host separator today.

**Why this priority**: Same defect, lower-consistency-cost surface: a human can read either
spelling, but two users comparing output should not see two spellings, and the error message
is where an operator copies the path from.

**Independent Test**: Under the same simulation, assert the text output of `charter generate`,
`charter interview` and a `_display_path()` caller contains no backslash, and that a path
outside the repository still renders as before.

**Acceptance Scenarios**:

1. **Given** a scratch repository, **When** `spec-kitty charter generate --from-interview` runs under the simulation, **Then** its `Charter: …` line reports `.kittify/charter/charter.md`.
2. **Given** a scratch repository, **When** `spec-kitty charter interview --defaults` runs under the simulation, **Then** its `Interview file: …` line reports `.kittify/charter/interview/answers.yaml`.
3. **Given** `--from-interview` with a missing or malformed `answers.yaml`, **When** `charter generate` fails under the simulation, **Then** the error message names `.kittify/charter/interview/answers.yaml`.
4. **Given** a path outside the repository, **When** `_display_path()` renders it, **Then** the out-of-repo fallback still applies and no `ValueError` escapes.

### Edge Cases

- **Path outside the repository.** `_display_path()` is also called with roots that are not the
  repo (a charter bundle elsewhere, a global pack). Its `ValueError` fallback must survive, and
  the fix must not turn a legal absolute path into a crash.
- **A caller that needs the native path.** The helper returns a *string*; file access keeps
  using the `Path` it already has. No access path may be built from the normalised string.
- **Pre-#6277 base.** The seam `kernel.charter_pack_paths.repo_relative_posix()` is introduced
  by #6277 (PR #7045), which is still open. This Mission needs the same seam on `main`, so it
  adds the identical function; whichever PR lands second keeps one definition.
- **POSIX output must not move.** `to_posix()` of a `PurePosixPath` is `str()` of it, so no
  existing Linux expectation changes; a golden that moves would be a regression, not a fix.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | POSIX `charter_path` in the generate envelope | As a machine consumer, I want `charter generate --json` to report a POSIX repository-relative path so that one parser reads every platform. | High | Open | [build] | no |
| FR-002 | POSIX `interview_path` in the interview envelope | As a machine consumer, I want `charter interview --json` to report a POSIX repository-relative path so that one parser reads every platform. | High | Open | [build] | no |
| FR-003 | One seam decides the spelling | As a maintainer, I want generate, interview and `_display_path()` to render through `kernel.charter_pack_paths.repo_relative_posix()` so that the rule is not hand-rolled per call site. | High | Open | [build] | no |
| FR-004 | Text output and the missing/malformed-interview message are POSIX | As an operator, I want the `Charter:`/`Interview file:` lines and the interview-answers error message to spell the path POSIX so that Linux and Windows output can be compared. | Medium | Open | [build] | no |
| FR-005 | Out-of-repo fallback preserved | As an operator whose charter state lives outside the repository, I want `_display_path()` to keep returning a usable path and never raise so that the status verbs still work. | Medium | Open | [ratchet] | yes — paired with FR-003's in-repo assertion on the same `_display_path()` call |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No envelope shape change | Field names, field set, ordering guarantees, exit codes and the printable-JSON contract of both envelopes stay byte-identical apart from the separator, so no consumer needs a version gate. | Compatibility | High | Open |
| NFR-002 | No behaviour change on POSIX | On a POSIX host every reported string is unchanged from `main`; the existing charter test suites pass without editing an expectation. | Reliability | High | Open |
| NFR-003 | Non-vacuity | The regression module carries a control proving the Windows-rendering simulation really produces a backslash for a bare `str(relative_to(...))`, so the module cannot pass without the fix. | Testability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| C-001 | Use the existing seam | The separator swap stays in `kernel.paths.to_posix()`; no site may hand-roll `str.replace("\\\\", "/")` or an ad-hoc `as_posix()` decision of its own. | Technical | High | Open |
| C-002 | No second spelling authority | The helper is defined once, in `kernel/charter_pack_paths.py`, and imported; the CLI layer does not grow a private copy. | Technical | High | Open |
| C-003 | Do not widen into #6277's scope | `charter synthesize`'s reporting surface and the committed `synthesis-manifest.yaml` belong to #6277 / PR #7045; this Mission changes only generate, interview and `_display_path()`. | Technical | High | Open |

### Key Entities

No new entity. The mission reshapes the *rendering* of an existing value — a repository-relative
path string — and adds one function to an existing kernel module.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Under the Windows-rendering simulation, both `--json` envelopes report a path string containing zero `\` characters, and equal the value POSIX produces — [build] · no-op passable: no
- **SC-002**: `charter generate`, `charter interview` and the missing/malformed-interview error report their path POSIX under the simulation — [build] · no-op passable: no
- **SC-003**: A path outside the repository still renders through `_display_path()`'s fallback without raising — [ratchet] · no-op passable: no
- **SC-004**: The pre-existing charter CLI test suites pass unchanged on a POSIX host — [ratchet] · no-op passable: no
