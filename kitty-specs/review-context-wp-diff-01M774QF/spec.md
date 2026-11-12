# Mission Specification: Review context carries the WP diff and cited requirement text

**Mission Branch**: `kitty/mission-review-context-wp-diff-01M774QF`
**Created**: 2026-11-12
**Status**: Draft
**Input**: Sub-epic #7578 (parent epic #7543). Ranked fixes 1 and 3 of the rc7 benchmark step register. Brief-intake mode: the issue, the dispatch brief, the research in `research/` and six operator rulings (Decision Moments `01M774W5…` to `01M774WE…`).

## Intent Summary (confirmed)

- **Primary actor**: an agent (or human) **reviewing one work package**. Secondary actor: the operator who consolidates the Mission.
- **Trigger**: the reviewer opens the review for a work package that was moved to `for_review`. Two entry points do this: `spec-kitty agent action review` and the `spec-kitty next` review step.
- **Desired outcome**: the reviewer knows, without searching, (a) exactly which commits and files make up *this* work package's implementation, and (b) the full text of every requirement the work package cites. The review prompt states the work package's own review range, lists its implementation commits and a per-file change summary, and gives the exact commands to read the change. It does **not** inline the diff and writes no diff file (operator ruling, Q1). The reviewer fetches the diff with those commands.
- **Rule that must always hold**: the review range is bounded at both ends by that work package's recorded window. It opens at the window opener (the same rule consolidation uses). It closes at the work package's newest submission for review. It is never empty when the work package has implementation commits, and never unbounded. When it cannot be determined, the prompt says so and names why.
- **Widened scope (operator ruling, Q3)**: a commit-to-target `single_branch` Mission records the window-open point and the submission point today records nothing for it. It will now record both, so the window is recorded, not derived, on every topology. The operator accepted the resulting change to consolidation inputs. The design keeps such Missions unbounded at consolidation unless planning shows otherwise, and any verdict change is named in the plan.
- **Out of scope**: the review template wording (owned by `spec-kitty-open-packs`; a follow-up is filed there), the pre-review regression gate and its evidence provenance (sub-epic E, #7547), any new gate, any change to a refusal code or exit code, and the for_review gate predicate (#5675, #5331, #6851).

## Domain Language

| Term | Meaning | Avoid |
|---|---|---|
| **Work-package window** | The span of a work package's work: it opens at its window opener (its first move to claimed/in-progress since it last returned to planned; a review rejection keeps the window) and closes at its newest submission for review. ADR `2026-11-08-2`. | "claim range" or "lane range" for this meaning |
| **Submission point** | The commit at the head of the work package's write branch when it was last moved to `for_review` (the `for_review` lane-head stamp). | "HEAD" (the live tip moves) |
| **Review range** | `window open..submission point`, scoped to the work package's owned files, with its provenance (recorded, derived, or unavailable). | "diff base" alone |
| **Owned files** | The work package's declared `owned_files` map. | |
| **Out-of-map path** | A path changed inside the review range that is outside the owned files. | |

## User Scenarios & Testing *(mandatory)*

### User Story 1: A reviewer on a single_branch Mission sees the work package's real change (Priority: P1)

A reviewer opens the review for WP02 of a `single_branch` Mission that commits to its target branch. Today the printed commands compare the target with HEAD, which is the same commit, so they print nothing. The reviewer then spends dozens of git commands looking for the implementation commit. After this Mission, the prompt names WP02's review range, lists WP02's implementation commits (and not WP01's or WP03's), shows a per-file change summary, and prints `git log` / `git diff` commands over exactly that range.

**Why this priority**: rank 1 of the benchmark register (score 20). It is the most expensive review friction measured.

**Independent Test**: build a `single_branch` commit-to-target fixture with three work packages committed in sequence, and review WP02. The prompt's commands, when run, return exactly WP02's implementation commits and files.

**Acceptance Scenarios**:

1. **Given** a commit-to-target `single_branch` Mission whose WP02 has two implementation commits between its claim and its submission for review, and WP03 has committed after them, **When** the reviewer opens WP02's review, **Then** the prompt lists exactly WP02's two commits, the per-file summary covers only WP02's owned files, and the printed commands span that range.
2. **Given** the same Mission on a protected target, with a minted Mission branch, **When** the reviewer opens WP02's review, **Then** the outcome is the same as in scenario 1.
3. **Given** either shape, **When** the reviewer runs the printed commands, **Then** their output is non-empty and contains no commit of another work package.

---

### User Story 2: A reviewer on a lanes Mission sees only this work package, not its lane-mates (Priority: P1)

On a `lanes` or `lanes_with_coord` Mission, a lane can carry several work packages. Today the commands span the whole lane from its base to HEAD. After this Mission, they span only this work package's window, scoped to its owned files. Any path the window touched outside the owned files is listed as a separate warning line, so nothing is hidden.

**Why this priority**: the same rank-1 defect on the other topologies. #7578 names all three topologies in its Done-when.

**Independent Test**: build a two-lane fixture where WP01 and WP02 share lane A and WP03 is on lane B. Review WP02: the range excludes WP01's commits and WP03's lane.

**Acceptance Scenarios**:

1. **Given** WP01 and WP02 run in sequence on one lane, **When** WP02 is reviewed, **Then** WP01's commits are not in the listed commits and its files are not in the summary.
2. **Given** WP02's window also changed a file outside its owned files, **When** WP02 is reviewed, **Then** that file appears in an "outside owned files" warning line and is not silently dropped.
3. **Given** a `lanes_with_coord` Mission, **When** a work package is reviewed from the repository root checkout, **Then** the range is still that work package's own window, not the coordination branch's.

---

### User Story 3: A reviewer sees the text of every cited requirement (Priority: P1)

The work package cites `FR-003, NFR-001, C-002`. Today the prompt lists only the IDs, so reviewers read `spec.md` and `plan.md` over and over: 104 reads in one benchmark, the largest group of review commands. After this Mission, the prompt carries the declared text of each cited requirement from the Mission's specification.

**Why this priority**: rank 3 of the benchmark register (score 16).

**Independent Test**: a work package citing FR, NFR, C and SC IDs. The prompt shows each ID with its declared text.

**Acceptance Scenarios**:

1. **Given** a work package citing `FR-003` and `NFR-001`, both declared in the spec, **When** it is reviewed, **Then** the prompt shows each ID with its declared title and statement.
2. **Given** a cited ID that the spec does not declare, **When** it is reviewed, **Then** the prompt shows the ID marked "not declared in this Mission's spec". It is never dropped.
3. **Given** a cited ID that names another Mission (`<slug>#FR-002`), **When** it is reviewed, **Then** the prompt labels it as a citation of another Mission and does not resolve it locally.

---

### User Story 4: Honest degradation when the window is not recorded (Priority: P2)

Some Missions have no recorded window. They predate window recording, or the window has a gap (the lane branch was missing at claim, a capture failed, or the recorded commit is no longer on the branch). The reviewer still gets the best available range, labelled with where it came from and why the recorded one is missing. When no range can be determined at all, the prompt states that plainly and names the reason. It never prints an empty or unbounded range.

**Why this priority**: the range must be trustworthy. A silently wrong range is worse than an honest notice.

**Independent Test**: fixtures for each gap kind, plus a pre-window Mission.

**Acceptance Scenarios**:

1. **Given** a work package whose window opener was recorded as "lane branch missing" and whose in-progress move recorded the open point, **When** it is reviewed, **Then** the range uses the recorded open point.
2. **Given** a Mission created before window recording, **When** a work package is reviewed, **Then** the range is derived from the commits that recorded its claim and its submission, and the prompt labels it "derived".
3. **Given** a work package with no determinable open point, **When** it is reviewed, **Then** the prompt says "review range unavailable: <reason>", and the review itself still proceeds. No new refusal is added.

---

### User Story 5: An operator's consolidation is unchanged by the new window recording (Priority: P3)

Commit-to-target `single_branch` Missions now record window points (Q3). The operator who consolidates such a Mission sees the same verdicts as before, unless the plan names a verdict change and the operator accepts it.

**Why this priority**: the operator accepted the change, but it should be visible and minimal.

**Independent Test**: re-run the existing consolidation and accept tests for commit-to-target `single_branch` Missions against the new recording.

**Acceptance Scenarios**:

1. **Given** a commit-to-target `single_branch` Mission whose work packages now carry recorded window points, **When** it is accepted and consolidated, **Then** the verdicts and refusal codes equal those before this Mission, or the difference is the one the plan recorded.

### Edge Cases

- **Rework after rejection.** A work package rejected and resubmitted has several submissions for review. The range runs from the window opener to the **newest** submission, so the reviewer sees the whole work-package change, not only the fix delta.
- **The branch moved after submission.** Commits landed after the submission point (another work package, or a fix committed during review). The range stops at the submission point, and the prompt says that the branch has moved past it and by how many commits.
- **Parallel claims on one lane.** The window is over-wide (a known residual, #5721). The owned-files scope keeps the summary honest, and the out-of-map line shows the spill.
- **A recorded open point that no longer resolves** (rebased or landed branch). It is treated as a gap: fall back and label it.
- **Bookkeeping-only commits** (status, issue matrix, Mission metadata) inside the range are left out of the listed implementation commits.
- **A work package with no owned files declared.** The range is unscoped and labelled as such, and the out-of-map line is omitted.
- **A planning-artifact work package on a lanes Mission** (it commits on the target branch). It gets no recorded window (not in Q3's scope), so it uses the derived range.
- **A very large window** (many files). The per-file summary is truncated with a count of omitted files. The commands still cover everything.
- **A requirement declared twice in the spec, or as a heading rather than a table row.** The canonical declaration is used, and duplicates are reported, never guessed.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | One review range per work package | As a reviewer, I want the review range computed from the work package's window, from window open to the newest submission point, so that it covers exactly this work package's change on every topology. | High | Open | [build] | no — the single_branch fixture prints an empty range today |
| FR-002 | Window recorded on commit-to-target single_branch | As a reviewer, I want a commit-to-target `single_branch` Mission to record the window-open point and the submission point (the write checkout's head at those moves), so that its range is recorded, not guessed. | High | Open | [build] | no — today these Missions record no window point |
| FR-003 | Same window rule as consolidation | As an operator, I want the review range to use the same window-opener rule consolidation uses, from one shared definition, so that review and consolidation judge the same commits. | High | Open | [build] | no — paired with the rework fixture: a last-claim rule differs from the window-opener rule after a rejection |
| FR-004 | Range provenance and honest fallback | As a reviewer, I want the prompt to say whether the range is recorded or derived (and why the recorded one is missing), or that no range is available and why, so that I never trust a silently wrong, empty or unbounded range. | High | Open | [build] | no — the gap fixtures show no provenance today |
| FR-005 | Implementation commits listed | As a reviewer, I want the work package's implementation commits listed (short SHA and subject), with bookkeeping-only commits left out, so that I do not hunt for them. | High | Open | [build] | no |
| FR-006 | Per-file change summary scoped to owned files | As a reviewer, I want a per-file change summary (lines added and removed) for the range, scoped to the owned files on every topology, so that I see the scope at a glance. | High | Open | [build] | no |
| FR-007 | Out-of-map paths surfaced | As a reviewer, I want paths changed in the range outside the owned files listed in a separate warning line, so that scoping hides nothing. | Medium | Open | [build] | no — paired with the in-map fixture |
| FR-008 | Exact review commands over the range | As a reviewer, I want the printed `git log` and `git diff` commands to use exactly the review range and owned paths, so that running them shows this work package's change and is never empty when it has implementation commits. | High | Open | [build] | no — the single_branch fixture prints an empty command today |
| FR-009 | Moved-branch note | As a reviewer, I want a note when the branch has moved past the submission point, with the commit count, so that I know the live tip differs from what was submitted. | Medium | Open | [build] | no |
| FR-010 | Cited requirement text | As a reviewer, I want the declared text of every requirement ID the work package cites (FR, NFR, C, SC and research kinds) shown in the prompt, so that I need not re-read the spec. | High | Open | [build] | no — the prompt shows bare IDs today |
| FR-011 | Unresolved and foreign citations labelled | As a reviewer, I want a cited ID not declared in the spec marked "not declared", and an ID of another Mission labelled as such, so that a citation is never dropped silently. | Medium | Open | [build] | no — paired with the declared-ID fixture |
| FR-012 | Both entry points agree | As a reviewer, I want `agent action review` and the `next` review step to show the same range, commits, summary, commands and requirement text, and the recorded review-prompt metadata to name the same base, so that the two paths cannot drift apart. | High | Open | [build] | no — the two paths use different bases today |
| FR-013 | Review never refused for a missing range | As a reviewer, I want the review to proceed with an "unavailable" notice when no range can be determined, so that this Mission adds no new refusal. | High | Open | [ratchet] | yes — paired with the gap fixture, whose notice text must appear |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Bounded prompt growth | The added review-context block (range, commits, summary, commands, out-of-map line) is at most 4 KB for a work package with up to 40 changed files and 20 commits. Beyond that, lists are truncated with an explicit omitted-count line. | Performance | High | Open |
| NFR-002 | Bounded latency | Building the review context adds at most 1.0 s (p95 over 10 runs) to review-prompt generation for a work package with up to 200 commits and 500 changed files in its range. | Performance | High | Open |
| NFR-003 | Requirement-text size | Each cited requirement's text is shown in full up to 600 characters, then truncated with a marker; 20 cited IDs add at most 12 KB. | Performance | Medium | Open |
| NFR-004 | Fail-soft | 0 new non-zero exits: every failure while resolving the range or the requirement text (git error, unreadable spec, unreadable status) degrades to a labelled notice in the prompt. | Reliability | High | Open |
| NFR-005 | Deterministic output | The same repository state yields byte-identical review-context blocks across two runs. | Reliability | Medium | Open |
| NFR-006 | Quality bar | New and changed code passes `ruff` and `mypy --strict` with no new suppressions, every function has complexity ≤ 15, and diff coverage of changed lines is at least 90%. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No diff body, no diff file | The prompt never inlines patch text and writes no diff file. The reviewer fetches the diff with the printed commands (operator ruling Q1). | Business | High | Open |
| C-002 | No new gate, no code changes | No new gate, refusal code, exit code or gate-severity change. | Technical | High | Open |
| C-003 | Templates are upstream | No edit under `packs/built-in/`. Template wording that goes stale is filed in `spec-kitty-open-packs`. | Technical | High | Open |
| C-004 | Pre-review gate untouched | The pre-review regression gate, its changed-file authority and its evidence provenance are not changed (sub-epic E, #7547). The for_review gate predicate is not changed. | Technical | High | Open |
| C-005 | One window rule | The window-opener rule has exactly one definition, shared by consolidation and review. No second selector. | Technical | High | Open |
| C-006 | Status read door | Review-side status reads go through the single status read door (ADR `2026-11-06-2`). | Technical | High | Open |
| C-007 | Layering | The enforced module chain and the runtime outbound ledger are not widened. Repository path listings go through the git owner's listing helpers. | Technical | High | Open |
| C-008 | ADR amendment | The new recording on commit-to-target `single_branch` (FR-002) is recorded as an amendment to ADR `2026-11-08-2`, together with its effect on consolidation (expected: none; such Missions stay unbounded at consolidation). | Technical | High | Open |
| C-009 | Planning lanes keep no stamp | Planning-artifact work packages on lane topologies keep recording no window. Only commit-to-target `single_branch` gains recording. | Technical | Medium | Open |
| C-010 | ATDD first | A failing acceptance test that drives the production review entry points on `single_branch`, `lanes` and `lanes_with_coord` fixtures is committed before any implementation. | Technical | High | Open |

### Key Entities

- **Review range**: base point, submission point, provenance (`recorded` / `derived` / `unavailable`), gap reason, owned-file scope, and the moved-past count.
- **Implementation commit**: short SHA, subject, and whether it is bookkeeping-only.
- **File change entry**: path, lines added, lines removed, and whether it is inside the owned files.
- **Cited requirement**: ID, kind, declared title or statement, and resolution (`declared` / `not declared` / `other Mission` / `ambiguous`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On `single_branch` (commit-to-target and minted), `lanes` and `lanes_with_coord` fixtures, 100% of reviewed work packages that have implementation commits get printed review commands that return a non-empty result containing only that work package's commits. — [build] · no-op passable: no
- **SC-002**: 100% of requirement IDs cited by a reviewed work package appear in the prompt with their declared text, or with an explicit "not declared" or "other Mission" label. — [build] · no-op passable: no
- **SC-003**: Both review entry points produce identical review-context blocks for the same work package and repository state in 100% of fixture cases. — [build] · no-op passable: no
- **SC-004**: Accept and consolidation verdicts for existing commit-to-target `single_branch` fixtures are unchanged (0 differences), or differ only as recorded in the plan. — [ratchet] · no-op passable: yes — paired with SC-001's commit-to-target fixture, which proves the new recording exists
- **SC-005**: In the next benchmark run (tracked, not gating), review-phase git discovery commands and `spec.md`/`plan.md` reads per review each fall by at least 50% against the rc7 register (about 100 and 104). — [build] · no-op passable: no

## Assumptions

- The newest submission for review is the right upper bound. The live branch tip is not (operator ruling Q2).
- Owned-file scoping applies on every topology, with out-of-map paths surfaced (ruling Q4).
- The window-opener rule moves, behaviour-preserving, to a home both consolidation and review can use (ruling Q5).
- No issue is folded (ruling Q6). Related: #3481, #3925, #7120, #7345, #5721. Excluded as gate policy: #6851, #5675, #5331.
- Every supported agent harness has shell access, so commands are enough. A harness without shell access is out of scope.

## Dependencies

- ADR `2026-11-08-2` (work-package windows) and its implementation (#7403, PR #7490).
- ADR `2026-11-06-2` (status read door, PR #7564, merged).
- ADR `2026-10-04-5` (approval stamp bound): the consolidation readers of the recorded stamps.
- Follow-up in `spec-kitty-open-packs`: review prompt wording that points at `<base>..HEAD` and at re-reading the spec.
