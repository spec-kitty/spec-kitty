# Mission Specification: Charter CLI tests independent of invoking checkout

**Mission Branch**: `issue-5317-charter-test-cwd-isolation`
**Created**: 2026-10-04
**Status**: Draft
**Input**: GitHub issues #5317 and #5601 (spec-kitty/spec-kitty), plus the operator's steer that both look like one cause and one fix could close both.

## Summary

A group of charter command tests pass when the test run starts in the repository root checkout and fail when the same run starts in a linked worktree. Every mission lane worktree is a linked worktree, so implementers and reviewers see the same false failures in every mission and classify them by hand.

The tests direct a charter command at a test tmp project, but they leave the process working directory in the invoking checkout. The charter write guard looks at the process working directory, sees a linked worktree, and refuses. The guard is right; the tests are not isolated.

This is the third time the problem has surfaced. The earlier fix (#4873) repaired individual files and left three copies of the same isolation helper. This mission gives that isolation one shared owner, applies it wherever it is needed, and adds a check so a new test cannot reintroduce the leak unnoticed. The product is not changed.

## Domain Language

These four terms are distinct and must not be merged in this mission's artifacts:

| Term | Meaning | Avoid |
|------|---------|-------|
| Process working directory | The directory the test process is running in. This is what the charter write guard probes. | "repo root", "cwd root" |
| Repository root checkout | The non-worktree checkout of a repository. | "main repo", "main repository" |
| Linked worktree | An additional checkout attached to a repository (every lane worktree is one). The guard refuses charter writes from it. | "worktree" used for any checkout |
| Test tmp project | The temporary project a test builds and directs a command at. | "tmp repo" when it is not a git repository |
| Invoking checkout | The checkout the test run was started from. | "the real repo" |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Lane-worktree runs report only real failures (Priority: P1)

A mission implementer or reviewer runs the charter and consolidation test files from inside a lane worktree, as the mission workflow requires. Tests that write a charter into a test tmp project pass there exactly as they do from the repository root checkout.

**Why this priority**: This is the reported defect in both issues. Each mission currently spends effort re-classifying the same false reds, and a real regression in these files would hide among them.

**Independent Test**: Start the affected test files from a linked worktree and from the repository root checkout of the same commit; both runs give the same results.

**Acceptance Scenarios**:

1. **Given** a test run started inside a linked worktree, **When** a test directs a charter write command at a test tmp project, **Then** the command acts on the test tmp project and is not refused because of the invoking checkout.
2. **Given** the test named in #5601, **When** it runs from a lane worktree, **Then** it passes.
3. **Given** the charter command test files named in #5317, **When** they run from a lane worktree, **Then** none fails with a linked-worktree write refusal.
4. **Given** the same test files, **When** they run from the repository root checkout, **Then** they still pass (no regression for the run that already worked).

---

### User Story 2 - The isolation has one owner (Priority: P2)

A contributor writing a new charter command test finds one shared isolation helper to use, with one description of what it does and when to use it. The three existing per-file copies are gone.

**Why this priority**: Three copies after one earlier fix is how the problem came back. One owner makes the right pattern the easy one to find.

**Independent Test**: Search the test suite for the isolation helper; exactly one definition exists, and the files that previously defined their own copy use the shared one and still pass.

**Acceptance Scenarios**:

1. **Given** the test suite, **When** a contributor looks for the charter working-directory isolation helper, **Then** there is exactly one definition.
2. **Given** the three files that carried their own copy, **When** they run, **Then** they pass using the shared helper, from both kinds of checkout.
3. **Given** a test that deliberately needs the invoking checkout's working directory, **When** it does not ask for the helper, **Then** its working directory is left alone.

---

### User Story 3 - A new leaking test is caught before a mission trips on it (Priority: P2)

A contributor adds a charter command test that directs a write command at a test tmp project without isolating the process working directory. An automated check in the ordinary test run fails for that test and names the test and the helper to use, even though that run is started from the repository root checkout where the leaking test itself would pass.

**Why this priority**: Ordinary runs and CI start from a repository root checkout and never see this failure, which is why it recurred. Without a check that fires there, the fix decays again.

**Independent Test**: Add a deliberately leaking test in a scratch copy; the check fails and names it. Remove it; the check passes.

**Acceptance Scenarios**:

1. **Given** a test that reaches a guarded charter write command while its process working directory is still in the invoking checkout, **When** it runs from any checkout, **Then** the check fails that test and names it. Detection is per test, not per file: a leaking test beside an isolated one in the same file is still caught.
4. **Given** a leaking test that reaches the command indirectly (through a helper function, a differently spelled patch, or arguments held in a variable), **When** it runs, **Then** it is caught the same way.
2. **Given** the suite after this mission, **When** the check runs, **Then** it passes with no exempted tests.
3. **Given** the check is not attached to one of the guarded write commands (for example a newly added one), **When** the suite runs, **Then** a test fails rather than the check passing silently.

---

### User Story 4 - The dry-run smoke test also runs from a lane worktree (Priority: P3)

The dry-run evidence smoke test starts the charter command as a separate process in the invoking checkout on purpose, so the shared helper does not apply to it. It is made independent of the kind of checkout by a change to the test only.

**Why this priority**: It is one test with a different shape. It belongs to the same reported symptom, but it must not pull a product decision into this mission.

**Independent Test**: Run the smoke test from a linked worktree and from the repository root checkout; it passes in both and still exercises the dry-run summary it was written to check.

**Acceptance Scenarios**:

1. **Given** the smoke test started from a linked worktree, **When** it runs, **Then** it passes and still makes both of its existing assertions (the dry-run evidence summary and the code signals line), with no skip, expected-failure mark or branch on the kind of checkout, and without borrowing another real checkout as its working directory.
2. **Given** no test-only remedy keeps the smoke test meaningful, **When** planning establishes that, **Then** the test is left unchanged, the reason is recorded, and a follow-up issue is filed; the product guard is not changed in this mission.

### Edge Cases

- A test tmp project that is itself a git repository (some suites initialise one) and one that is a plain directory: the isolation works for both.
- A test that calls a guarded write command and then a read command in the same test (two of the reported failures are read-command tests that fail in their preparatory write step).
- A file where some tests need the isolation and others need the invoking checkout's working directory.
- A test that reaches the guarded command indirectly, through a shared helper function rather than a direct call, so a naive check would miss it.
- A test that legitimately asserts the guard's refusal from a real linked worktree: it must keep working and must not be flagged by the check.
- The affected set is open-ended. Other files with the same leak that were not listed in either issue are in scope when found.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Shared isolation helper | As a contributor, I want one shared, opt-in test helper that makes a test's process working directory and the project root it directs charter commands at come from the same test tmp project, so that the charter write guard sees the test tmp project and not the invoking checkout. | High | Open | [build] | no — a reproduction that starts in a real linked worktree fails without the helper |
| FR-002 | Reproduction through the existing entry point | As a reviewer, I want a test that builds a real linked worktree, starts from inside it, and drives a charter write command at a test tmp project through the existing command entry point, so that the defect is witnessed from any checkout. The witnessed failure is the command's own linked-worktree refusal message in its output; a collection, import or missing-helper error does not count. The unisolated arm stays afterwards as a permanent assertion that the refusal happens without the helper. | High | Open | [build] | no — the unisolated arm shows the refusal and the isolated arm succeeds on the same fixture |
| FR-003 | Retire the per-file copies | As a contributor, I want the three existing per-file copies of the isolation helper removed in favour of the shared one, so that there is exactly one definition. | High | Open | [build] | no — a count of definitions is checked |
| FR-004 | Adopt in every affected test | As an implementer in a lane worktree, I want every test that directs a guarded charter write command at a test tmp project to use the shared helper, so that these tests give the same result from a linked worktree and from the repository root checkout. This covers the files named in #5317 and #5601 and any other file with the same leak. | High | Open | [build] | no — the listed tests are red from a linked worktree before the change |
| FR-005 | Recurrence check | As a maintainer, I want an automated check in the ordinary test run that fails any test which reaches a guarded charter write command while its process working directory is in the invoking checkout, naming the test and the shared helper, so that the leak cannot return unnoticed in runs started from a repository root checkout. Detection is per test and does not depend on how the test spells its setup. | High | Open | [build] | no — self-mutation tests plant one offender per shape (direct call, call through a helper, alternative patch spelling, leaking test beside an isolated one) and each is caught; a coverage test fails if any guarded write command is not watched |
| FR-006 | Check starts with no exemptions | As a maintainer, I want the recurrence check to ship with no exempted tests, so that it records no standing debt. | High | Open | [build] | no — the suite is searched for uses of the exemption and none is allowed |
| FR-007 | Dry-run smoke test independent of checkout kind | As an implementer in a lane worktree, I want the dry-run evidence smoke test to pass from a linked worktree by a test-only change that keeps both of its existing assertions, uses no skip, expected-failure mark or branch on checkout kind, and does not use another real checkout as its working directory; or, if no such change keeps it meaningful, a recorded deferral with a follow-up issue. | Medium | Open | [build] | no — the test is red from a linked worktree before the change |
| FR-008 | Guard still runs under the helper | As a maintainer, I want proof that the shared helper does not disable the guard: with the helper active, a test that then moves into a linked worktree and runs a guarded write command is still refused. The existing guard test files are left with zero changes and keep passing. | High | Open | [ratchet] | yes for the unchanged guard tests — paired with the with-helper refusal control, which a stubbed guard would fail |
| FR-010 | Pinned-rule inventory stays consistent | As a maintainer, I want the release pinning inventory, which records one of the per-file copies being retired, re-derived and its entry given an explicit disposition, so that the inventory freshness check stays green and the retired copy leaves no stale record. | Medium | Open | [build] | no — the freshness check is red once the copy is removed and green after re-derivation |
| FR-009 | Issue matrix records both issues and the moot half | As the operator, I want the mission's issue matrix to carry a row for #5317 and #5601, and to record #5317's acceptance-test half as verified with no work owed, so that the closing verdicts are traceable. | Medium | Open | [build] | no — the matrix rows are checked at approval |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Same results from both checkout kinds | The affected test files give identical pass/fail results when started from a linked worktree and from the repository root checkout of the same commit: 0 differences, with no test skipped or marked expected-failure in one run and not the other, and no skip or expected-failure mark added by this mission. | Reliability | High | Open |
| NFR-002 | Check is cheap | The recurrence check completes in under 5 seconds on a developer machine and runs in the ordinary fast test tier. | Performance | Medium | Open |
| NFR-003 | No added run time for unaffected tests | The shared helper is opt-in; tests that do not request it are unaffected, and no test file's run time grows by more than 10%. | Performance | Low | Open |
| NFR-004 | Actionable failure | A recurrence-check failure names the offending file and the shared helper by name in a single message, so the fix needs no further investigation. | Usability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No product change | Nothing under the product source tree (`src/`) changes. Maintenance scripts that derive test inventories are not product source. The charter write guard, its probe point (the process working directory) and repository-root resolution stay exactly as they are (charter-catalog-coherence-01M2XQQF#FR-006, charter-catalog-coherence-01M2XQQF#C-002). | Technical | High | Open |
| C-002 | No bypass of the guard in tests | Tests must not replace or stub the guard itself to get green. Isolation works by putting the process in the test tmp project, so the real guard still runs. | Technical | High | Open |
| C-003 | Opt-in, not blanket | The shared helper is requested by the tests that need it. It is not applied to the whole suite, because some tests need the invoking checkout's working directory. | Technical | High | Open |
| C-004 | Single owner | The isolation is defined once. No new per-file copy is introduced. | Technical | High | Open |
| C-005 | No fixed test count as the contract | The affected set is open-ended; requirements are stated by pattern (guarded write command directed at a test tmp project), not by a count of tests. | Process | Medium | Open |
| C-006 | Targeted test runs only | Mission work runs the named test files and the specific gate files it touches, not whole directories or full suites. | Process | Medium | Open |

### Key Entities

- **Shared isolation helper**: the single opt-in test helper that ties a test's process working directory and its project root to one test tmp project.
- **Guarded write command**: a charter command whose write guard probes the process working directory and refuses when it is a linked worktree. Today these are the charter generate, synthesize and resynthesize commands. Charter activate and deactivate probe the project root they were given instead; that root is derived from the process working directory when a test supplies none, so the recurrence check watches them as well.
- **Recurrence check**: the automated check that fails a test which reaches a guarded write command from the invoking checkout.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Started from a lane worktree, the test files named in #5317 and #5601 report zero linked-worktree write refusals. — [build] · no-op passable: no
- **SC-002**: The same files started from the repository root checkout report the same results as from a lane worktree: zero differences, and no skip or expected-failure mark added. — [build] · no-op passable: no
- **SC-003**: Exactly one definition of the isolation helper exists in the test suite, down from three. — [build] · no-op passable: no
- **SC-004**: A planted leaking test is reported by the recurrence check in a run started from a repository root checkout, where the planted test itself would pass. — [build] · no-op passable: no
- **SC-005**: The product source tree (`src/`) is unchanged by this mission: zero changed files. — [ratchet] · no-op passable: yes, paired with SC-001 on the same run (the reds go green with no product change)
- **SC-006**: Both issues can be closed by the mission's pull request, with #5317's acceptance-test half recorded as verified and owing no work. — [build] · no-op passable: no

## Assumptions

- The operator delegated this mission end to end from the two issues; the discovery answers come from the issues and the pre-spec grounding run, not from an interview.
- The acceptance-test half of #5317 could not be reproduced, on current `main` or at the issue's own base commit (24 passed from a linked worktree in both). It is treated as verified with no work owed.
- Decision recorded for the dry-run smoke test: test-only remedy, product guard unchanged (decision `01M43CMN0GADTHK0Q378QYK2WE`). The operator may reverse this at pull-request review.

## Out of Scope

- Whether a dry run should be refused from a linked worktree (a product question).
- `test_interview_mapping_mission_alias` failing from a linked worktree: a different cause, see #5140.
- Known defects of the guard itself: see #5411 and #4250.
- Other commands that read the process working directory directly.
- A scheduled run of the whole suite from a real linked worktree.
- Tests that start a guarded write command as a separate process: the recurrence check cannot see them. Only the dry-run smoke test does this today, and FR-007 covers it.

## Context

- Follow-up: the earlier per-file fix was #4873, landed by PR #5173.
- The guard was introduced for #4785; see ADR `2026-08-12-1` ("charter authoring stays at the repository root").
- Parent epic of #5317: see #5105.
