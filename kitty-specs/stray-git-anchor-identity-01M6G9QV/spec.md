# Mission Specification: A stray `.git` name is not an identity refusal

**Mission Branch**: `stray-git-anchor-identity-01M6G9QV`
**Created**: 2026-11-03
**Status**: Draft
**Input**: Issue spec-kitty/spec-kitty#7084 — `tests/lanes/test_refinalize_mission_branch.py` reports `skip` where the test expects `wrote`. Mission guidance: fix the subject, not the assertion; decide from the code and its history whether the command or the test is wrong, and say which and why.

## Context

`backfill_mission` (the command behind `migrate backfill-identity` and the upgrade seams) refuses to
mint a `mission_id` when it believes git holds a copy it cannot give back (#6673). Grounding showed
the trust decision is made by scanning ancestor directory **names**: if any ancestor carries a `.git`
entry, the mission is treated as "tracked but unreadable" and skipped. A `.git` name that is not a
repository — an empty directory, a leftover lock/hook home — therefore blocks identity backfill for
every mission below it, with a refusal whose own remedy (`git checkout -- meta.json`) cannot be run.
The issue's `tests/lanes` failure and a second failure in the `read_tracked_meta` contract tests are
both this defect. Full evidence: `<mission_dir>/research.md`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Backfill mints an identity where git holds nothing (Priority: P1)

An operator backfills a legacy mission whose `kitty-specs/<slug>/` folder git does not track, on a
machine where some ancestor directory carries a `.git` entry that is not a repository (for example
`/tmp/.git`, which spec-kitty's own fallbacks leave behind). The mission is given an identity and
the command says it wrote one.

**Why this priority**: without it the mission can never acquire an identity, and the operator is
told to run a restore command that has nothing to restore. Every mission under such a path — a
whole test session's worth — is blocked.

**Independent Test**: create a mission folder with an identity-less `meta.json` below a temp root
that has a non-repository `.git` directory above it, call `backfill_mission`, and assert
`action == "wrote"` with a minted id now on disk.

**Acceptance Scenarios**:

1. **Given** a `kitty-specs/<slug>/meta.json` without `mission_id`, no git repository anywhere above
   it, and an unrelated directory named `.git` above it, **When** the operator runs
   `backfill_mission`, **Then** the result is `action="wrote"`, `mission_id` is a fresh ULID, and
   `meta.json` on disk carries it.
2. **Given** the same folder with **no** ancestor `.git` at all (the pre-existing behaviour),
   **When** the operator runs `backfill_mission`, **Then** the result is still `action="wrote"` with
   a fresh id (nothing regressed).
3. **Given** the issue's own fixture (`tests/lanes/test_refinalize_mission_branch.py`), **When** the
   suite runs on a host whose temp root carries a stray `.git` directory, **Then** the file is
   green, and the recorded mission branch stays byte-identical across the refinalize that follows.

---

### User Story 2 - The tracked-identity refusal still fails closed where git may hold the identity (Priority: P1)

A maintainer runs the same backfill on a mission whose identity git may hold but cannot produce —
a `.git` marker file pointing at an unavailable worktree gitdir, a staged-but-uncommitted copy, a
corrupt committed copy, or a repository home git refuses to read. The command still refuses with its
coded notice, so no second identity is minted over one the history uses.

**Why this priority**: the #6673 contract is a safety property. Widening "nothing tracked" must not
widen it over a real repository.

**Independent Test**: for each shape above, assert `action == "skip"`, a `reason` carrying the
`TRACKED_META_*` code, and an unchanged `meta.json`; paired with a positive control on the same
fixture where git does hold a usable copy (the identity is taken back).

**Acceptance Scenarios**:

1. **Given** a mission folder whose ancestor `.git` is a *file* (`gitdir:` pointer) that git cannot
   follow, **When** the tracked metadata is read, **Then** it is reported as unavailable (refusal),
   not as "nothing tracked".
2. **Given** a mission folder whose ancestor `.git` is a *directory carrying `HEAD`* that git
   refuses to read, **When** the tracked metadata is read, **Then** it is reported as unavailable
   (refusal).
3. **Given** a usable tracked copy, or a corrupt/staged one, **When** the operator backfills,
   **Then** the identity is taken back from git or refused with its code, exactly as today.

---

### Edge Cases

- An ancestor `.git` **directory without `HEAD`** (only `hooks/`, `spec-kitty-locks/`, nothing a
  repository needs) is not a repository home: it must not turn into a refusal.
- An ancestor that cannot be stat'ed (`OSError`) keeps the fail-closed behaviour: it counts as an
  anchor.
- A `.git` directory carrying `HEAD` but missing `objects/` stays a refusal: the shape is a broken
  repository, and a mint there would be as unrecoverable as the refusal. No behaviour change is
  required, and no test is added for it beyond the anchor-shape row.
- A missing `meta.json` (not merely identity-less) keeps its existing `"meta.json not found"` skip
  reason; this mission does not touch that path.
- `GIT_CEILING_DIRECTORIES`-bounded walking and the `kernel/ancestor_walk` refactor belong to
  in-flight PR #7082; this mission changes only *what counts as an anchor*, so the two compose.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | A non-repository `.git` is not an anchor | As an operator backfilling a mission under a path that merely contains a `.git` entry, I want the identity minted so that the mission stops being unbackfillable. | High | Open | [build] | no |
| FR-002 | A `.git` that can be a repository home still refuses | As a maintainer, I want the tracked-identity refusal to keep firing where git may hold a copy, so that no second identity is minted over the one history uses. | High | Open | [ratchet] | yes — positive control: the same fixture's usable tracked copy is still taken back (`test_a_present_copy_that_lost_its_identity_takes_the_tracked_one["usable"]`) |
| FR-003 | The issue's failing node is green on a polluted host | As a maintainer, I want `tests/lanes/test_refinalize_mission_branch.py` green without editing its assertions, so that the reported red is gone for the reason it is red. | High | Open | [build] | no |
| FR-004 | The anchor rule is stated where it is implemented | As a reviewer, I want the predicate's rule and its fail-closed cases documented beside the code so that the next reader does not re-derive them from behaviour. | Medium | Open | [build] | yes — the same-fixture refusal/ mint tests are the control that the docstring describes real behaviour |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No added filesystem walks | The fix adds no new ancestor walk and no new git invocation: at most two `stat` calls per ancestor visited by the existing loop, so the probe's cost on a deep path stays within one filesystem pass. | Performance | Medium | Open |
| NFR-002 | Fail-closed on the unknown | Every ancestor state that cannot be read (`OSError`) or that could be a repository home still yields a refusal; the number of refusal-triggering shapes may only shrink for shapes that are provably not repositories. | Reliability | High | Open |
| NFR-003 | Deterministic under ambient state | The identity path's verdict depends only on the mission path and the git answers for it, not on unrelated `.git` entries elsewhere in the tree: two runs of the same fixture under different ambient `.git` shapes produce the same `action`. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Scope is the anchor predicate | Only `specify_cli/mission_metadata.py`'s anchor probe changes; `backfill_mission`, the refusal notices and their codes stay as they are. | Technical | High | Open |
| C-002 | The #6673 contract is not weakened | Refusals that protect a real tracked identity (usable, corrupt, staged, index-only, unreadable repo) keep their behaviour and their pins. | Business | High | Open |
| C-003 | Compose with the in-flight walk refactor | Do not introduce a hand-rolled root walk or ceiling logic; PR #7082 replaces the loop and adds a gate against hand-rolled walks. | Technical | High | Open |

### Key Entities

- **Anchor**: an ancestor `.git` entry that could be a repository home for the mission folder. Its
  shape decides between "git may hold a copy" (refuse) and "git holds nothing" (mint).
- **Tracked metadata read** (`TrackedMeta`): the probe's answer — usable copy, unavailable/fail
  closed, or nothing tracked.
- **Backfill result** (`BackfillResult.action`): `wrote` when an identity was minted or taken back,
  `skip` when nothing needed writing or the call refused.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `uv run pytest tests/lanes/test_refinalize_mission_branch.py -q` is 11 passed on a host whose temp root carries a non-repository `.git` directory, with no edit to the test's assertions. — [build] · no-op passable: no
- **SC-002**: `uv run pytest tests/specify_cli/upgrade/test_read_tracked_meta_6673.py tests/specify_cli/migration/test_backfill_identity_tracked_absent_6673.py tests/integration/migration/test_upgrade_tracked_meta_identity_6673.py -q` is fully green, including the refusal fixtures this mission must not weaken. — [ratchet] · no-op passable: yes — positive control: the same files' refusal cases fail if a refusal-triggering shape is removed
- **SC-003**: The new regression test is red before the fix and green after it, and the paired refusal test stays green in both states (proof the widening is confined to non-repositories). — [build] · no-op passable: no
