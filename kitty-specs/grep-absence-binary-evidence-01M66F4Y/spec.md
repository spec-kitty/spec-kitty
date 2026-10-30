# Mission Specification: grep_absence must judge tracked text and record named evidence

**Mission Branch**: `issue-6761-grep-absence-binary-evidence`
**Created**: 2026-10-30
**Status**: Draft
**Input**: Issue spec-kitty/spec-kitty#6761 — "acceptance grep_absence counts a stale .pyc 'binary file matches' as still_present, with empty evidence". Guidance (operator): fix the matcher so it judges tracked text, make the evidence name what matched, reproduce the stale-`.pyc` case red-first. The related issues #2743 and #5464 track different defects in the same checker and are out of scope.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Operator accepts after removing offending text (Priority: P1)

An operator runs `spec-kitty accept` on a mission whose negative invariant (type
`grep_absence`) targets a string the mission removed from every tracked source
file. Even though the test suite already ran once and a stale `.pyc` under
`__pycache__/` still contains the old string, the invariant must verify as
`confirmed_absent`, because gitignored bytecode is not the tracked surface the
invariant judges.

**Why this priority**: This is the reported defect — the false `still_present`
blocks `accept` after the work is done.

**Independent Test**: A fixture repo whose tracked `.py` no longer contains the
pattern but whose `__pycache__/*.pyc` does; running the real
`acceptance-verdict --execute` path must record `confirmed_absent`.

**Acceptance Scenarios**:

1. **Given** a repo where every tracked file is free of the pattern and a stale
   `.pyc` under `__pycache__` still contains it, **When** the negative invariant
   is executed, **Then** the verdict is `confirmed_absent` (binary files are
   skipped, e.g. `grep -I`).
2. **Given** a repo where a tracked text file still contains the pattern,
   **When** the negative invariant is executed, **Then** the verdict is
   `still_present` and the evidence names the matching file(s) — the existing
   positive control, kept working.

### User Story 2 - Evidence is never empty on a non-absent verdict (Priority: P1)

An operator reading a `still_present` or `verification_error` verdict in
`acceptance-matrix.json` can see *what* matched or what went wrong. When grep
exits 0 with empty stdout (e.g. GNU grep ≥ 3.5 printing `binary file matches`
on stderr), the recorded evidence includes the stderr content, so it is never
`grep found matches: ` with nothing after it.

**Why this priority**: The empty evidence is the second half of the reported
defect — the operator cannot diagnose the block.

**Independent Test**: A fixture where grep exits 0 with empty stdout and
non-empty stderr must produce evidence that includes that stderr text.

**Acceptance Scenarios**:

1. **Given** grep exit code 0 with empty stdout and stderr containing
   `binary file matches`, **When** the evidence string is recorded, **Then** it
   includes the stderr content (e.g. names the binary file grep flagged).
2. **Given** grep exit code 0 with stdout matches, **When** the evidence string
   is recorded, **Then** it still lists the first matching lines as before.

### Edge Cases

- The pattern genuinely appears in a **tracked text** file (e.g. mission prose
  or docs): the verdict stays `still_present` — binary skipping must not weaken
  the text search. Positive control on the same fixture.
- grep cannot start (missing binary) or exits with code ≥ 2: existing
  `verification_error` behavior is unchanged.
- A scoped invariant (`scope` set): binary skipping and evidence rules apply
  identically under the declared search roots.
- Repos with no `__pycache__` or no binary files at all: behaviour is
  byte-identical to today for the text-match path.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Binary files are skipped by the grep_absence matcher | As an operator, I want the negative-invariant grep to judge tracked text only, so a stale `.pyc` cannot keep a removed string "present". | High | Open | [build] | no — red-first repro: stale `.pyc` present, tracked text clean, must be `confirmed_absent` |
| FR-002 | Non-absent verdicts carry non-empty evidence naming what matched | As an operator, I want the evidence to name what grep saw, so I can diagnose a blocked `accept` instead of reading an empty match list. | High | Open | [build] | no — paired with the same-fixture positive control of FR-003 |
| FR-003 | A tracked text match still yields still_present with named matches | As an operator, I want a genuine text occurrence to keep blocking accept with named evidence, so the invariant cannot be weakened by the fix. | High | Open | [ratchet] | no — positive control on the same fixture as FR-001 |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No surface change | The CLI flags, the `NegativeInvariant` dataclass fields and the `acceptance-matrix.json` schema are unchanged; only verdict/evidence values produced by the grep method change. | Compatibility | High | Open |
| NFR-002 | Same process model | The matcher still shells out to system `grep` once per invariant execution; no new dependency or Python-side tree walk. | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Out of scope: sibling defects | #2743 (unknown verification_method loops pending) and #5464 (stale verdict never re-checked) are separate issues and must not be folded in. | Scope | High | Open |
| C-002 | Red-first proof | The stale-`.pyc` reproduction is added as a failing test through the pre-existing `acceptance-verdict` entry point before the fix lands. | Process | High | Open |

### Key Entities

- **NegativeInvariant**: unchanged shape (`invariant_id`, `description`,
  `verification_method`, `verification_command`, `scope`, `result`, `evidence`).
  Only the values the grep method writes into `result`/`evidence` change.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: With every tracked file free of the pattern and a stale `.pyc` under `__pycache__` containing it, executing the invariant through the real `acceptance-verdict --execute` path records `confirmed_absent`. — [build] · no-op passable: no
- **SC-002**: With a tracked text file containing the pattern, executing the invariant records `still_present` with evidence naming the matching file. — [ratchet] · no-op passable: no
- **SC-003**: When grep exits 0 with empty stdout and non-empty stderr, the recorded evidence includes that stderr content verbatim (truncated as today). — [build] · no-op passable: no
