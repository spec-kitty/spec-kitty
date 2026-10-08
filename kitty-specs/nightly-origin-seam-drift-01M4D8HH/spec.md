# Mission Specification: Nightly red: test seams after origin freshness

**Mission Branch**: `issue-5888-nightly-test-seam-drift`
**Created**: 2026-10-08
**Status**: Draft
**Input**: Nightly run 37723696665 (head `4cabb904`) went red in 16 tests across three groups (#5886, #5887, #5888, #5889). The previous nightly (37567676962 at `ecc257f4`) was green. Research (`research.md`) bisected every group to PR #5845 (#5780, origin freshness) and found the product change intended and the test seam stale.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The nightly is an honest signal again (Priority: P1)

A maintainer reads the nightly result to decide whether `main` can be released. Today 16 tests fail for test-seam reasons, not product defects, so a red nightly hides any real regression behind known noise.

**Why this priority**: Red CI == no release (charter Standing Order #9). The reds must be cleared at the root, never retried or skipped.

**Independent Test**: Run the 16 failing node ids on the branch; all pass, and each one failed on the merge base.

**Acceptance Scenarios**:

1. **Given** current `main`, **When** the 16 node ids run, **Then** all 16 fail with the errors recorded in the issues.
2. **Given** this mission's branch, **When** the same node ids run, **Then** all 16 pass, and so do the rest of their test files.

### User Story 2 - Machine consumers of `accept --json` keep one JSON payload on stdout (Priority: P2)

An orchestrator pipes `spec-kitty accept --json` stdout into a JSON parser. The origin-freshness note added in #5845 must go to stderr and to the payload's `advisories`, never ahead of the JSON.

**Independent Test**: An owned-checkout `accept --diagnose --json` whose clone has remote-tracking refs but no remote yields parseable stdout. The note appears on stderr and in `advisories`.

**Acceptance Scenarios**:

1. **Given** an owned checkout with remote-tracking refs and no remote, **When** `accept --diagnose --json` runs, **Then** stdout parses as one JSON object, stderr carries the "no remote is configured" note, and `advisories` includes it.

### Edge Cases

- The doctrine git-source recorder runs out of scripted results: the fallback result must still match the caller's `text=` mode (bytes for `kernel.git.run_git`).
- The `core.sshCommand` reads are local config reads, not contacts. The recorder must not count them as GitSource's git calls, or record their environment as a contact environment.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Doctrine git-source recorder models the ssh-command read | As a maintainer, I want `TestGitSource` to script only GitSource's own git contacts so that the `core.sshCommand` reads `no_prompt_env` makes (`dc4524a5`) do not consume scripted results. | High | Open | [ratchet] | no — the 7 node ids fail on the merge base |
| FR-002 | Merge golden pins `--origin-check` | As a maintainer, I want the consolidate flag-surface golden to include the intended `--origin-check` flag (`73682930`, ADR 2026-10-06-3) so that it detects real drift again. | High | Open | [ratchet] | no — fails on the merge base |
| FR-003 | Accept harness stands in for the origin gate | As a maintainer, I want the accept decomposition harness to fake `run_origin_gate` like every other collaborator (`9ed59d9c`) so that the owned-entry tests characterise accept, not placement on a stub, and the owned fact is shown to reach the gate. | High | Open | [ratchet] | no — 2 node ids fail on the merge base |
| FR-004 | Owned-checkout accept tests parse stdout | As a maintainer, I want the explicit-checkout integration tests to parse `result.stdout` (the `--json` contract) so that the stderr origin note (`460ba7c8`) does not break parsing, and one test pins the note on stderr and in `advisories`. | High | Open | [ratchet] | no — 6 node ids fail on the merge base |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Lint/format/type clean | The changed files pass `ruff check`, `ruff format --check --force-exclude` and mypy with zero new issues and no new suppressions. | Quality | High | Open |
| NFR-002 | No product change | Zero lines change under `src/`. | Scope | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No skip/xfail/retry | No test is skipped, xfailed, quarantined or retried to reach green. | Process | High | Open |
| C-002 | Out of scope | #5891 (performance shard: #5894 / PR #5895, #5753) is not touched. | Scope | High | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 16 node ids listed in #5886, #5887, #5888 and #5889 pass on the branch, and each failed on the merge base. — [ratchet] · no-op passable: no
- **SC-002**: The four touched test files pass in full on the branch. — [ratchet] · no-op passable: no
