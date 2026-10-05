# Mission Specification: Approved claim bound

**Mission Branch**: `issue-5668-approved-claim-bound`
**Created**: 2026-10-04
**Status**: Draft
**Input**: spec-kitty/spec-kitty #5668 — `consolidate` lands commits made on a lane after the work package was approved and prints "Reconciliation verified".
**Grounding**: [research/code-grounding.md](research/code-grounding.md) (five-lens pre-spec squad, reproduced on `main` at `9adc68803f`).

## Intent Summary

- **Actor**: the operator (or orchestrating agent) who runs `spec-kitty consolidate` on a mission whose work packages are approved.
- **Trigger**: a lane branch holds a commit that was added after its work package was approved, so nobody reviewed it.
- **Today**: the commit lands on the target, the command exits 0 and prints "Reconciliation verified".
- **Desired outcome**: `consolidate` refuses, names the commit and says how to get it reviewed. "Verified" is printed only when what landed is what review approved.
- **Invariant**: the commit recorded when a work package was approved is the single reference for what review approved. Nothing later on the lane is approved work.
- **Discovery**: the operator's brief replaced the interview. The grounding squad's open questions were settled from the brief and are recorded in the Assumptions section and in section 6 of the grounding document.

## Domain Language

| Term | Meaning | Avoid |
|---|---|---|
| **Approval stamp** | The lane head recorded on a work package's `approved` transition (`policy_metadata.lane_head`). | "latest stamp" (the `done` transition restamps with the landed tip) |
| **Approved bound** | For one lane: the approval stamp that is furthest along the lane among its approved work packages. | "lane tip" |
| **Post-approval commit** | A commit on the lane after the approved bound that carries content and did not arrive through a merge from a known source. | "late commit" without the qualifier |
| **Unstamped approval** | An approval whose transition carries no approval stamp (recorded by a release before 4.0.0rc5, or the stamp could not be taken). | "legacy mission" |
| **Attestation** | An operator's recorded statement, with a reason, that an unstamped approval covers the lane as it stands now. | "override", "force" |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A post-approval commit is refused (Priority: P1)

An implementer still has the lane worktree after the reviewer approved WP01. They commit one more file. The operator runs `spec-kitty consolidate`. The command refuses before any branch moves, names the commit and the work package, and tells the operator to move the work package back for review.

**Why this priority**: this is the defect. Unreviewed code reaches the target under a "verified" banner.

**Independent Test**: build a mission through the real lane allocator and status transitions, approve WP01, commit a file on the lane, run `consolidate` as a subprocess. The same fixture without the extra commit must consolidate and print the banner.

**Acceptance Scenarios**:

1. **Given** a `lanes` mission with WP01 approved, **When** a content commit is added to WP01's lane and `consolidate` runs with the default strategy, **Then** it exits non-zero with error code `LANE_MOVED_AFTER_APPROVAL`, names the commit and WP01, states the re-review remedy, prints no "Reconciliation verified" line, and the target branch is unchanged.
2. **Given** the same mission, **When** `consolidate --strategy merge` runs, **Then** the outcome is the same.
3. **Given** a mission with a coordination branch in the same state, **When** `consolidate` runs with either strategy, **Then** the outcome is the same.
4. **Given** the same fixture with no commit after approval, **When** `consolidate` runs, **Then** it exits 0, prints "Reconciliation verified" and the approved content is on the target.
5. **Given** a mission that passes the up-front check, **When** a content commit is added to an approved lane after that check and before the lane is merged (injected at a named phase boundary of a real `consolidate` run), **Then** the run exits non-zero with `LANE_MOVED_AFTER_APPROVAL`, prints no "Reconciliation verified" line and leaves the target at its pre-run tip. With the up-front check alone this scenario stays red.
6. **Given** a mission with code lanes and a post-approval commit, **When** `orchestrator-api consolidate-mission` runs, **Then** it returns its `PREFLIGHT_FAILED` envelope with `LANE_MOVED_AFTER_APPROVAL` as the reported code and no lane is merged.
7. **Given** a lane that mixes an approved and a canceled work package, **When** the lane has a content commit made after the approval and outside every work package's work, **Then** `consolidate` refuses: with the existing mixed-lane refusal and its unchanged text when that fires, otherwise with `LANE_MOVED_AFTER_APPROVAL`.

---

### User Story 2 - An unstamped approval fails closed, and the operator can attest (Priority: P1)

A mission was approved with a release that did not record the approval stamp. The operator upgrades and runs `consolidate`. The command refuses and names the work package. The operator either sends the work package back through review, or inspects the lane and attests with a reason. After the attestation the mission consolidates; a commit added after the attestation is still refused.

**Why this priority**: without a stamp there is nothing to bound the claim. Passing such a mission would keep the defect open for every in-flight mission.

**Independent Test**: build a stamped mission, strip the approval stamps, run `consolidate`; then attest and run it again; then add a commit and run it again.

**Acceptance Scenarios**:

1. **Given** an approved work package with no approval stamp, **When** `consolidate` runs, **Then** it exits non-zero with error code `APPROVAL_STAMP_MISSING`, names the work package and both remedies, and the target is unchanged.
2. **Given** that mission, **When** the operator runs `consolidate --attest-approved-reviewed WP01 --attest-reason "<why>"`, **Then** the attestation is recorded in the status log with the reason and the lane head at that moment, and the mission consolidates.
3. **Given** an attested work package, **When** a content commit is added to its lane and `consolidate` runs, **Then** it refuses with `LANE_MOVED_AFTER_APPROVAL`.
4. **Given** a stamped work package whose lane has a post-approval commit, **When** the operator passes `--attest-approved-reviewed` for it, **Then** the request is refused and nothing is recorded.
5. **Given** a work package that reached `done` or counts as approved without any `approved` transition (for example a forced move), **When** `consolidate` runs, **Then** it refuses with `APPROVAL_STAMP_MISSING`; the `done` stamp is never used as the bound.
6. **Given** an attested work package, **When** the same run records its `approved -> done` transition and the gate re-checks, or the run is resumed, **Then** the attestation still holds.

---

### User Story 3 - Ordinary lane movement after approval still consolidates (Priority: P2)

Spec Kitty itself moves lanes after approval: it merges a dependency lane or the target into a stale lane, it resumes an interrupted consolidation, and a second work package on the same lane is approved later. None of these is unreviewed work, and none may be refused.

**Why this priority**: a fail-closed rule that refuses the tool's own bookkeeping would make `consolidate` unusable.

**Independent Test**: one test per movement, each asserting a clean consolidation on a fixture that also refuses when a real post-approval commit is added.

**Acceptance Scenarios**:

1. **Given** a lane with WP01 approved and then WP02 implemented and approved on the same lane, **When** `consolidate` runs, **Then** it consolidates.
2. **Given** an approved lane that received a merge from its dependency lane or from the mission base after approval, **When** `consolidate` runs, **Then** it consolidates.
3. **Given** a consolidation interrupted after a lane was merged, **When** `consolidate --resume` runs, **Then** the bound check does not refuse the tool's own merge commits.
4. **Given** a work package that was approved, sent back, reworked and approved again, **When** `consolidate` runs, **Then** the bound is the latest approval and the rework lands.

---

### Edge Cases

- The lane was rewritten after approval (rebase, force-push), so the approval stamp is no longer on the lane: refused with `APPROVAL_STAMP_NOT_ON_LANE`; remedy is re-review.
- A commit lands on a lane while `consolidate` is running, after the up-front check: the gate re-checks before it prints "verified", refuses and rolls back through the existing rollback authority.
- A lane mixes an approved and a canceled work package: the existing mixed-lane refusals keep their precedence, codes and texts.
- A post-approval commit that touches only mission bookkeeping files: not refused.
- A planning lane or a `single_branch` mission: not checked; see Known residuals.
- A code lane whose lane branch is missing: refused (existing behaviour), never treated as exempt.
- A dependent lane that carries its dependency lane's commits: those commits are accepted only when the dependency lane is itself bounded and checked in the same run.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Approval stamp is the authority | As an operator, I want the commit recorded at approval to be the one reference for what review approved, so that the gate and any other consumer agree. The approved claim of a lane is bounded by the lane's approved bound; one reader resolves it and every consumer uses that reader. | High | Open | [build] | no |
| FR-002 | Post-approval commit refused up front | As an operator, I want `consolidate` to refuse a lane that holds a post-approval commit before any branch moves, with error code `LANE_MOVED_AFTER_APPROVAL`, the commit(s) and work package(s) named, and the remedy "move the work package back for review", so that unreviewed code cannot land. | High | Open | [build] | no |
| FR-003 | Gate re-check during the run | As an operator, I want the reconciliation gate to refuse lane content that arrived after the up-front check (it compares each lane tip with the tip validated up front), so that a commit added while `consolidate` was running is refused by name and the run is rolled back through the existing rollback authority. | High | Open | [build] | no |
| FR-004 | "Verified" is honest | As an operator, I want "Reconciliation verified" printed only when every landed lane tip was within its approved bound, so that the word means the landed content is the approved content. | High | Open | [folded] — satisfied by FR-002 and FR-003, checked by SC-002 | no — paired with the clean-run positive control on the same fixture |
| FR-005 | Unstamped approval fails closed | As an operator, I want every work package in the approved claim that has no non-migration `approved` transition, or whose latest one carries no approval stamp, refused with error code `APPROVAL_STAMP_MISSING`, naming the work package and the two remedies (re-review, or attest), so that a missing stamp never passes silently. | High | Open | [build] | no |
| FR-006 | Attestation for an unstamped approval | As an operator, I want `--attest-approved-reviewed <WP>` with `--attest-reason` to record my statement in the status log and lift only the missing-stamp refusal for that work package, with the lane head at attestation as its bound, so that I can land a mission approved before the stamp existed. The attestation holds until a later non-migration transition of that work package other than the consolidation's own `done` record. | High | Open | [build] | no |
| FR-007 | Attestation never lifts a post-approval commit | As a reviewer, I want an attestation request for a stamped work package refused, and a commit made after an attestation still refused, so that review stays the only way to approve content. | High | Open | [build] | no |
| FR-008 | Rewritten lane refused | As an operator, I want a lane whose approval stamp is no longer an ancestor of its tip refused with error code `APPROVAL_STAMP_NOT_ON_LANE` and the re-review remedy, so that a rebase after approval cannot swap the content. | Medium | Open | [build] | no |
| FR-009 | Tool-made lane movement is not refused | As an operator, I want merges from a dependency lane, the mission base or the target, commits that touch only paths the reconciliation gate already classes as bookkeeping (one shared definition, not a second one), a later approval on the same lane, and a resumed consolidation to pass the check, so that the rule refuses only unreviewed work. A dependency lane's commits are accepted only when that lane is itself bounded and checked in the same run. | High | Open | [build] | yes — each case is paired with a refusing control on the same fixture |
| FR-010 | Latest approval wins | As a reviewer, I want the bound taken from the latest approval of each work package, ignoring migration events and the `done` restamp, so that rework approved again lands and the landed tip never becomes its own bound. | High | Open | [build] | no |
| FR-011 | Every landing entry point is covered | As an integrator, I want `consolidate --resume` to apply the same refusals as `consolidate`, and `orchestrator-api consolidate-mission` to evaluate the FR-002, FR-005 and FR-008 check before its first lane merge on both its planning-only and its code-lane path and report the code in its `PREFLIGHT_FAILED` envelope, so that no entry point lands a post-approval commit. | High | Open | [build] | no |
| FR-012 | Existing refusals unchanged | As an operator, I want every existing refusal code and text byte-identical, and the mixed-lane refusals evaluated first on a mixed lane (when none fires, FR-002, FR-005 and FR-008 still apply), so that current remedies and scripts keep working. | High | Open | [ratchet] | yes — pinned by the existing canceled-content, closed-world and residual tests, which must stay in their current state |
| FR-013 | Red-first reproduction through the CLI | As a maintainer, I want a regression test that runs `spec-kitty consolidate` on a fixture with a post-approval commit, for squash and merge strategies and for lanes and coordination topologies, committed red before the fix. | High | Open | [build] | no |
| FR-014 | Truthful approval fixtures | As a maintainer, I want the shared consolidation test fixtures to record approvals after the lane work exists, with real approval stamps, and the tests that assert the live-tip claim retired or rewritten, so that the suite can express "after approval" and no longer encodes the defect. | High | Open | [build] | no |
| FR-015 | Decision and operator documentation | As an operator, I want the new refusals, the attestation flag and the upgrade impact documented (CLI reference, changelog, decision record), so that I know what to do when `consolidate` refuses. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Bounded extra cost | A consolidation with no canceled work package reads the status event log once for the claim (a test counts the reads); the existing canceled-content benchmark test stays within its current budget. | Performance | Medium | Open |
| NFR-002 | Code quality | Every new or changed function has cyclomatic complexity of 15 or less and passes `ruff` and `mypy --strict` with zero findings and no new suppressions. | Maintainability | High | Open |
| NFR-003 | Coverage | Changed lines are covered at 90% or more by tests in the same pull request. | Maintainability | High | Open |
| NFR-004 | Refusals are non-destructive | 100% of the new refusals leave the target, mission and coordination branches at their pre-run tips, and each names a remedy that destroys no work. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | One rollback authority | No new restore path. Any rollback goes through the existing rollback authority; its allowed-caller pin stays unchanged. | Technical | High | Open |
| C-002 | Status stays git-free | The status transition pipeline gains no git access; the reader of the approval stamp lives with the existing stamp readers on the consolidation side. | Technical | High | Open |
| C-003 | No fail-open fallback | An absent approval stamp is never replaced by the live lane tip, in product code or through a test-only switch. | Technical | High | Open |
| C-004 | No new ratchet or size gates | The mission adds no allowlist, baseline or size gate. | Process | High | Open |
| C-005 | Scope of the bound | Every code lane is bounded. Only planning lanes (per the lanes manifest) and `single_branch` missions are exempt; a code lane whose branch is missing is refused, not exempted. | Technical | Medium | Open |
| C-006 | Tracker hygiene | Issue priorities are not changed. Only #5668 is closed by this mission. | Process | Medium | Open |
| C-007 | Red before fix | The reproduction test is committed before the fix, after any behaviour-preserving tidy-up commits. | Process | High | Open |

### Key Entities

- **Approval stamp**: per work package; the lane head recorded on its latest `approved` transition.
- **Approved bound**: per lane; derived from the approval stamps of the lane's approved work packages and from attestations.
- **Attestation record**: an operator transition in the status log carrying the reason and the lane head at that moment; voided by a later non-migration transition of the same work package, except the consolidation's own `done` record.

## Known residuals (out of scope, each tracked)

- **Between two approvals on one lane.** A commit made after WP01's approval and before WP02 is claimed on the same lane sits under WP02's later bound. Closing it needs per-work-package windows on every lane.
- **Content inside a merge commit.** A merge commit that itself carries new content is not seen; pinned as a strict expected-failure test.
- **Commit during review.** The stamp is the lane head when the approval was recorded, not the commit the reviewer read.
- **Lanes without a lane branch.** Planning lanes and `single_branch` missions are not stamped and not bounded.
- **Width of "bookkeeping".** The gate's existing bookkeeping definition covers the repository's `.kittify/` tree and any `kitty-specs/<slug>/` path segment. A post-approval commit confined to those paths is not refused. The bound reuses that definition so there is one authority; narrowing it is a separate change to the existing content checks.
- **Orchestrator path has no gate re-check.** `orchestrator-api consolidate-mission` has no rollback door, so on its code-lane path only the up-front check applies.
- **Dry-run forecast.** `consolidate --dry-run` does not report the new refusals (Follow-up: see #5329).

## Related work (context only)

Parent epic #5001. See #5330, #5331, #5333, #5337, #5446 and #4941 for adjacent open work; the for_review gate (see #5331, #5675) shares the flaw class but not the mechanism and is not changed here.

## Assumptions

- The operator's brief stands in for the discovery interview; its "Done when" list is the acceptance contract.
- A post-approval commit always goes back for review; attestation exists only for a missing stamp.
- The up-front refusal and the gate re-check use the same predicate.
- On a lane that mixes an approved and a canceled work package, the existing refusals fire first.
- `orchestrator-api consolidate-mission` gains no attestation flag; it reports the refusal and the operator attests through `consolidate`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In all four combinations (lanes or coordination topology, squash or merge strategy), a mission with a post-approval commit is refused and 0 files from that commit are on the target. — [build] · no-op passable: no
- **SC-002**: "Reconciliation verified" appears in 0 of the refused runs and in 100% of the clean control runs on the same fixtures. — [build] · no-op passable: no
- **SC-003**: An unstamped approval is refused in 100% of runs until re-reviewed or attested, and an attested mission consolidates. — [build] · no-op passable: no
- **SC-004**: The existing canceled-content, closed-world and rollback-authority tests pass unchanged in verdict, and the #5330 expected-failure tests keep their state. — [ratchet] · no-op passable: yes — positive control: the new refusing tests run on the same builders
- **SC-006**: `orchestrator-api consolidate-mission` merges 0 lanes of a code-lane mission that has a post-approval commit and reports `LANE_MOVED_AFTER_APPROVAL`. — [build] · no-op passable: no
- **SC-005**: The issue's reproducer script exits 0 ("fixed") in all four combinations. — [build] · no-op passable: no
