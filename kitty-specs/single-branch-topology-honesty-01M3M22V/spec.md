# Mission Specification: Single-branch topology honesty and destroyed-lane tip guard

**Mission Branch**: `issue-5100-single-branch-topology`
**Created**: 2026-09-28
**Status**: Draft (post-spec squad folded)
**Input**: This is the operator brief for slice 4 of the 4.0.0rc5 remediation (#5100, #4828, #2602, #5115). It is bound by the operator decision record on #5100 (comment 5870360497, "option E"). The spec was written in brief-intake mode: the decision record serves as the confirmed Intent Summary, and this spec does not reopen it.

## Intent Summary

- **Primary actor:** an operator (human or agent) who drives a mission through `spec-kitty agent mission create`, `implement`, `move-task`, and `consolidate`.
- **Trigger:** either of two situations.
  - A mission's stored topology is `single_branch`.
  - A `lanes` or flat mission had its lane worktree and branch destroyed while a work package was still in flight.
- **Desired outcome:**
  - A `single_branch` mission truly has no code lanes. Every work package runs one after another in the mission's write checkout. Status and code land on the same declared branch, and nothing is left behind on an undeclared branch.
  - A destroyed lane that still held unmerged committed work is refused loudly. It is not quietly re-cut as an empty lane.
- **Invariant:** the stored topology is the only authority for the execution surface.
  - No runtime fallback reinterprets a mission's topology from its artifacts.
  - A mission whose metadata and lane manifest disagree fails closed until it is migrated.

## Domain Language

| Term | Meaning in this mission | Avoid |
|------|-------------------------|-------|
| **Topology** | The shape a mission is given at creation (`single_branch`, `lanes`, `coord`, `lanes_with_coord`), stored in `meta.json`. | "mode", "layout" |
| **Write checkout** | The one checkout a `single_branch` mission writes code and status into. It is either the repository root checkout or a validated owned checkout (ADR 2026-09-03-1). | "main repo", "main repository" |
| **Repo-root lane** | The single bookkeeping lane of a `single_branch` mission, which keeps the existing lane id `lane-planning`. It always resolves to the write checkout, never to a `.worktrees/` path. It generalises today's planning lane. | "lane-a" for single_branch |
| **Code lane** | A lane that resolves to a `.worktrees/` lane worktree. Only `lanes`, `lanes_with_coord` and flat missions have code lanes. A repo-root lane is never a code lane. | — |
| **Protected target** | A target branch that is the repository's primary branch, or one that `ProtectionPolicy` reports as protected. Both are answered by one query on `ProtectionPolicy`. No forge API is consulted. | "main" as a generic name |
| **Mission branch** | `kitty/mission-<slug>-<mid8>`. It is minted and checked out in the write checkout, and recorded in `meta.json`, only when a `single_branch` mission targets a protected branch without the commit-to-target override. | — |
| **Lane work tip** | The last commit made on a lane branch. It is recorded when the commit happens, independent of any spec-kitty command. It is distinct from the lane's creation base. | "head"; "lane tip" when the base is meant |
| **Absorbed lane** | A lane whose work tip is an ancestor of the target, or whose merge into the target would change nothing (for example, after a squash merge). | "merged" (overloaded) |
| **Execution-mode stamp** | The `execution_mode` recorded on status events: `worktree` or `direct_repo`. This is not the work-product kind (`code_change` / `planning_artifact`), which older code also calls `execution_mode`. | bare "execution_mode" when the kind is meant |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Planning-artifact work never demands a lane-planning ref (Priority: P1)

An operator moves a `planning_artifact` work package to `for_review`, or implements a code work package that depends on one. Today two things go wrong:
- The for_review gate predicts a `.worktrees/<slug>-lane-planning` path that never exists, and rejects the WP.
- Dependency merge resolves the planning lane to `main`, not to the mission's target branch.

**Why this priority**: this problem is independent of the topology decision and small to fix, yet it currently forces `--force` onto legitimate transitions.

**Independent Test**: use a mission with one planning_artifact WP and one code WP that depends on it, on a target branch other than `main`.

**Acceptance Scenarios**:

1. **Given** a planning_artifact WP in progress with a committed deliverable, **When** it is moved to `for_review`, **Then** the gate passes without `--force`, and no `.worktrees/*-lane-planning` path is consulted.
2. **Control for scenario 1:** **Given** a planning_artifact WP with no committed deliverable, **When** it is moved to `for_review`, **Then** the gate still refuses it.
3. **Given** a code WP that depends on a planning_artifact WP, with target `feat/x`, **When** its lane is allocated, **Then** the dependency merge uses `feat/x`. A repository with no `main` branch neither warns nor skips.
4. **Given** any caller that asks for the planning lane's branch without naming the target branch, **When** the name is resolved, **Then** it is refused instead of silently returning `main`.

---

### User Story 2 - A single_branch mission runs in its write checkout (Priority: P1)

An operator explicitly creates a `single_branch` mission on an unprotected target, finalises its tasks, and implements WP01 and then WP02.

**Why this priority**: this is the P0 defect (#5100). Today code commits land on an undeclared lane branch in a `.worktrees/` checkout, while status lands on the declared branch.

**Independent Test**: `tests/integration/test_issue_5100_single_branch_topology.py`, driven through the real CLI. The same file includes a control mission using `lanes` topology.

**Acceptance Scenarios**:

1. **Given** a two-WP `single_branch` mission, **When** finalize-tasks runs, **Then** the lane manifest holds exactly one repo-root lane and no code lane.
2. **Given** that mission, **When** `implement WP01` runs, **Then** all of the following hold:
   - It exits 0 and WP01 is `in_progress`.
   - No `.worktrees/*-lane-*` directory is created.
   - No `kitty/mission-*` ref is created.
   - The resolved workspace is the write checkout.
   - The claimed and in_progress events are stamped `direct_repo`.
3. **Control for scenario 2:** **Given** a `lanes` mission with the same fixture, **When** `implement WP01` runs, **Then** a lane worktree is created and the events are stamped `worktree`.
4. **Given** WP01 in progress with committed work, **When** it is moved to `for_review`, **Then** the move succeeds without `--force`, and the for_review event is stamped `direct_repo`.
5. **Control for scenario 4:** a WP with no commit is still refused.
6. **Given** WP01 is `in_progress`, **When** `implement WP02` runs, **Then** it is refused with an error naming WP01, and nothing is created.
7. **Given** a second `single_branch` mission sharing the same write checkout has a WP `in_progress`, **When** `implement` runs for this mission, **Then** it is refused with an error naming that other mission's WP.
8. **Given** the write checkout has uncommitted changes outside spec-kitty-owned paths, **When** `implement` starts a new `single_branch` WP, **Then** it is refused and the dirty paths are named. Re-running `implement` on the WP that is already `in_progress` is a no-op resume and is not refused.
9. **Given** WP02 depends on WP01, **When** `implement WP02` runs after WP01 is approved, **Then** no dependency merge is performed. Dependency readiness is still enforced.

---

### User Story 3 - A single_branch mission on a protected target gets a mission branch (Priority: P1)

An operator creates a `single_branch` mission whose target is protected, for example the primary branch.

**Why this priority**: this is part of the binding decision (the amendment to item 4). Without it, a single_branch mission would commit straight onto a protected branch.

**Independent Test**: the same integration file, covering the protected-target case and the override-flag case.

**Acceptance Scenarios**:

1. **Given** a `single_branch` mission created against a protected target without the override, **When** the mission is created, **Then** all of the following hold:
   - `kitty/mission-<slug>-<mid8>` is created and checked out in the write checkout.
   - The branch name is recorded in `meta.json`.
   - No worktree is created.
   - All later planning, status and code commits land on that branch.
2. **Given** that mission, **When** `implement WP01` runs, **Then** it proceeds in the write checkout on the mission branch. If the checkout is on another branch or is dirty, it refuses and names the expected branch or the dirty paths.
3. **Given** the same mission created with the commit-to-target override, **When** it is created and implemented, **Then** no mission branch is created, and work happens on the target branch.
4. **Given** a mission branch with that name already exists, **When** the mission is created, **Then** creation is refused and names the branch.
5. **Given** a completed protected-target `single_branch` mission, **When** it is consolidated, **Then** all of the following hold:
   - The mission branch lands onto the target branch.
   - The repository root checkout and the target branch survive.
   - The checkout is switched back to the target branch before the mission branch is removed.
6. **Given** a completed unprotected-target `single_branch` mission, **When** it is consolidated, **Then** no branch is merged or deleted. Only bookkeeping (done transitions, mission number) runs.

---

### User Story 4 - New missions on feature branches default to lanes (Priority: P2)

An operator creates a mission on a non-primary branch without passing `--topology`.

**Why this priority**: decision item 2 and #2602. `single_branch` must be an explicit choice so that users on the default path keep worktree isolation.

**Independent Test**: mission-create unit tests for the default derivation.

**Acceptance Scenarios**:

1. **Given** a non-primary current branch and no `--pr-bound`, **When** a mission is created without `--topology`, **Then** its topology is `lanes`.
2. **Given** `--pr-bound` and a context where coordination is not reachable, **When** a mission is created without `--topology`, **Then** its topology is `lanes`.
3. **Given** `--topology single_branch` or `--owned-checkout`, **When** a mission is created, **Then** its topology is `single_branch`.
4. **Given** the primary branch, or `--pr-bound` where coordination is reachable, **When** a mission is created without `--topology`, **Then** it keeps the existing `coord` default.

---

### User Story 5 - Existing single_branch missions with code lanes are migrated, not reinterpreted (Priority: P1)

An operator upgrades a project that contains `single_branch` missions whose lane manifest already has code lanes. This repository has 64 such missions at mission start.

**Why this priority**: decision item 3. Without it, the new single_branch semantics would quietly re-route missions already in flight.

**Independent Test**: a migration test in which a `single_branch` mission with code lanes is re-stamped to `lanes`, while an unmigrated one fails closed.

**Acceptance Scenarios**:

1. **Given** a `single_branch` mission whose lane manifest has code lanes, **When** the upgrade migration runs, **Then** its stored topology becomes `lanes`, and no other `meta.json` field changes.
2. **Control for scenario 1:** **Given** a `single_branch` mission with only a repo-root lane, or with no manifest, **When** the migration runs, **Then** the mission is left unchanged.
3. **Given** an unmigrated `single_branch` mission with code lanes, **When** finalize-tasks writes a manifest or any command allocates a lane worktree for it, **Then** it fails closed with the `SINGLE_BRANCH_CODE_LANES_UNMIGRATED` error naming the remedy, and no worktree is created.
4. **Given** such missions exist, **When** the doctor topology check runs, **Then** it reports each one with that finding code and the remedy.
5. **Control for scenario 4:** a clean `single_branch` mission is not reported.

---

### User Story 6 - A destroyed lane with unmerged work is refused (Priority: P1)

A WP in an operator's `lanes` (or flat) mission is in flight. Work was committed on its lane with a plain `git commit`, and then the lane worktree and branch were deleted.

**Why this priority**: #5115, P0. Today the base-reachability check is always true for non-coord topologies. The lane is quietly re-cut empty, and the committed work is stranded.

**Independent Test**: `tests/lanes/test_issue_5115_destroyed_lane_non_coord.py`, driven through the real CLI.

**Acceptance Scenarios**:

1. **Given** a `lanes` mission with WP01 `in_progress`, a plain `git commit` on its lane, and then the lane worktree and branch deleted (with no spec-kitty command run in between), **When** `implement WP01` runs, **Then** all of the following hold:
   - It exits non-zero with a destroyed-lane error.
   - The error names the stored work-tip SHA and a restore command.
   - No new worktree is created.
   - The lane is not classified as absorbed.
2. **Given** a lane whose work was squash-merged into the target, after which its branch and worktree were removed, **When** `implement` re-opens that WP, **Then** it proceeds.
3. **Given** a lane whose work tip is an ancestor of the target (normal merge), **When** it is re-opened, **Then** it proceeds.
4. **Control:** **Given** a destroyed lane whose work tip equals its creation base (no work committed), **When** it is re-opened, **Then** it proceeds.
5. **Given** the lane's workspace record has been deleted (for example by context cleanup), **When** the destroyed lane is re-opened, **Then** the guard still refuses on the recorded tip. It does not fail open.
6. **Given** a project upgraded from a version that recorded no tips, **When** a lane with a live branch is next touched, **Then** its tip is recorded from the branch. A non-terminal WP whose lane is already gone and whose tip is unknown fails closed with an unknown-tip error.

### Edge Cases

- **Protection config changes after create:** protection is evaluated at `mission create`, and the outcome is recorded in `meta.json`. A later config change does not move an already-created mission branch.
- **Write checkout on the wrong branch:** `implement` refuses and names the expected branch. It never switches the checkout on its own.
- **Owned checkout under `.worktrees/`:** a `single_branch` mission with a validated owned checkout there treats that checkout as the write checkout. It is not treated as a lane worktree, and a mission branch (if needed) is checked out in it.
- **`--no-verify` and rebases:** a lane commit made with `--no-verify`, or during a rebase or cherry-pick, still records the tip.
- **`git merge`, `git pull` or `git reset` by the operator on a lane:** these are not recorded at commit time, but spec-kitty records the tip at its next lane touch. A lagging tip still points at the lane's own work, so this fails safe.
- **Hooks disabled, or a foreign post-commit hook present:** spec-kitty never overwrites a foreign hook. It warns, and tip recording falls back to spec-kitty's own lane touches. This is the documented residual.
- **Old git:** on a git version too old to evaluate absorption, the guard fails closed.
- **Flat missions (no `lanes.json`):** unaffected by the single_branch changes. They keep their existing fail-closed `MissingLanesError`.
- **Re-stamped missions:** after the migration they change from uncommitted to committed status annotations, because that is `lanes` behaviour. This change is expected.
- **Coord and `lanes_with_coord` missions:** unchanged.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Planning lane never needs a lane-planning worktree | As an operator, I want a planning_artifact WP with a committed deliverable to reach for_review without any lane-planning worktree or ref, while a WP without one is still refused, so that I never need `--force` for it. | High | Open | [build] | no — paired with the no-deliverable control |
| FR-002 | Planning-lane branch always resolves to the target | As an operator, I want every resolution of the planning lane's branch (dependency merge, approved-dependency refs) to use the mission's target branch, and a resolution that names no target to be refused, so that nothing silently merges `main`. | High | Open | [build] | no |
| FR-003 | single_branch finalize writes one repo-root lane | As an operator, I want finalize-tasks on a single_branch mission to write a manifest with exactly one repo-root lane holding every WP and no code lane, so that gates and consolidate keep a single reader. | High | Open | [build] | no |
| FR-004 | single_branch WPs resolve to the write checkout | As an operator, I want every single_branch WP (code or planning) to resolve to the write checkout — the validated owned checkout when one is recorded, else the repository root checkout — so that code and status land on the same declared branch. | High | Open | [build] | no — paired with the `lanes` control |
| FR-005 | direct_repo execution-mode stamp | As an operator, I want the claimed, in_progress and for_review events of a single_branch WP stamped `direct_repo`, and a `lanes` WP's stamped `worktree`, on every transition path (implement, workflow, move-task, orchestrator), so that history records where work executed. | High | Open | [build] | no — paired with the `lanes` control |
| FR-006 | No lane artefacts on an unprotected target | As an operator, I want implement on an unprotected-target single_branch mission to exit 0 with the WP in_progress while creating no lane worktree and no `kitty/mission-*` ref, so that nothing is created outside the declared surface. | High | Open | [build] | no — paired with the `lanes` control that does create one |
| FR-007 | Mission branch on a protected target | As an operator, I want mission create for a protected-target single_branch mission to mint and check out `kitty/mission-<slug>-<mid8>` in the write checkout (no worktree), record it in `meta.json`, route every later write to it, and refuse when that branch already exists, so that no commit lands directly on a protected branch. | High | Open | [build] | no |
| FR-008 | Commit-to-target override | As an operator, I want a mission-create flag `--commit-to-target`, persisted in `meta.json` and honoured through the existing protection authority, that makes a protected-target single_branch mission commit directly to its target, so that I can opt out deliberately. | Medium | Open | [build] | no |
| FR-009 | Dirty write checkout refused | As an operator, I want implement starting a new single_branch WP to refuse when the write checkout has uncommitted changes outside spec-kitty-owned paths, naming them, while a resume of the already in-progress WP is not refused, so that WP work never mixes with unrelated edits. | High | Open | [build] | no |
| FR-010 | One in-progress WP per write checkout | As an operator, I want implement to refuse a single_branch WP while any WP of any single_branch mission sharing the same write checkout is in progress, naming it, so that sequential execution is enforced. | High | Open | [build] | no |
| FR-011 | for_review works without --force | As an operator, I want a single_branch WP with committed work to move to for_review without `--force`, while one with no commit is still refused, so that the normal lifecycle works. | High | Open | [build] | no — paired with the no-commit control |
| FR-012 | Consolidate a protected-target single_branch mission | As an operator, I want consolidating a protected-target single_branch mission to land its mission branch onto the target, attribute authored content from the mission branch's history, switch the write checkout back to the target, and never remove the repository root checkout or the target branch, so that completed work reaches the target safely. | High | Open | [build] | no |
| FR-013 | Explicit-only single_branch create default | As an operator, I want a mission created without `--topology` on a non-primary branch — or with `--pr-bound` where coordination is unreachable — to default to `lanes`, with single_branch only from `--topology single_branch` or `--owned-checkout`, so that default users keep worktree isolation. | High | Open | [build] | no |
| FR-014 | Re-stamp migration | As an operator, I want a one-time upgrade migration to re-stamp every single_branch mission whose lane manifest has code lanes as `lanes`, changing no other field, so that in-flight missions keep their execution surface. | High | Open | [build] | no — paired with the unaffected-mission control |
| FR-015 | Doctor topology finding | As an operator, I want the doctor topology check to report `SINGLE_BRANCH_CODE_LANES_UNMIGRATED` for each affected mission with the remedy, and nothing for a clean single_branch mission, so that drift is visible. | Medium | Open | [build] | no — paired with the clean control |
| FR-016 | Unmigrated missions fail closed at the chokepoints | As an operator, I want writing a lane manifest with code lanes, or allocating a lane worktree, for a single_branch mission to fail closed with `SINGLE_BRANCH_CODE_LANES_UNMIGRATED`, with no runtime fallback, so that no command (implement, review, move-task, workflow, orchestrator, finalize-tasks) silently reinterprets a mission. | High | Open | [build] | no |
| FR-017 | Lane presence means code lanes | As an operator, I want topology derivation from artifacts (backfill, the derived-topology reader) to count only code lanes, so that a single_branch mission's own repo-root lane never reclassifies it as `lanes`. | High | Open | [build] | no |
| FR-018 | Record the lane work tip at commit time | As an operator, I want every commit on a lane branch — including `--no-verify` commits, amends, rebases and cherry-picks — and every lane advance spec-kitty performs, to record the lane work tip in a place that survives deletion of the lane branch, worktree and workspace record, so that destroyed work can be detected and restored. | High | Open | [build] | no |
| FR-019 | Destroyed-lane guard keys on the work tip | As an operator, I want implement on a destroyed lane with a non-terminal WP to refuse, naming the recorded tip and a restore command, when that tip is neither an ancestor of the target nor absorbed by it, creating nothing, so that committed work is never silently stranded. | High | Open | [build] | no — paired with FR-020 and the tip-equals-base control |
| FR-020 | Absorbed lanes stay re-openable | As an operator, I want a lane whose tip is an ancestor of the target, or whose merge into the target would be a no-op (squash absorbed), or whose tip equals its creation base, to remain re-openable, so that the guard has no false positives. | High | Open | [build] | no |
| FR-021 | Tip backfill for pre-existing lanes | As an operator, I want lanes that predate tip recording to have their tip recorded from the live branch the next time spec-kitty touches them, and a non-terminal WP whose lane is already gone and whose tip is unknown to fail closed, so that upgraded clones are guarded too. | High | Open | [build] | no |
| FR-022 | Single lane-record writer | As an operator, I want every lane allocation path (implement and the orchestrator API) to go through the one allocator that persists the workspace record, so that orchestrator-driven lanes are guarded too. | Medium | Open | [build] | no |
| FR-023 | Topology documentation is truthful | As a contributor, I want CLAUDE.md and `docs/architecture/execution-lanes.md` to state that single_branch has no computed code lanes, and a topology glossary entry under `docs/context/`, so that docs match shipped behaviour. | Medium | Open | [build] | no |
| FR-024 | Tip-recording hook preserves user hooks | As an operator, I want the commit-time tip recorder installed into the repository's effective hooks directory only when no foreign hook occupies that slot, with a warning otherwise, so that my own hooks are never overwritten. | High | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Commit-time tip recording is cheap | Recording the tip adds at most 50 ms (p95) to a lane commit, runs without starting a Python interpreter, and never changes a commit's exit status. | Performance | High | Open |
| NFR-002 | CLI latency unchanged | `implement` on a single_branch WP completes in under 2 seconds on a typical project (excluding the operator's own hooks). | Performance | Medium | Open |
| NFR-003 | Migrations are idempotent | Running the re-stamp twice yields byte-identical `meta.json` files to running it once; 0 fields other than `topology` change across the 64 in-repo missions. | Reliability | High | Open |
| NFR-004 | Refusals are actionable | 100% of new refusals (dirty checkout, in-progress WP, destroyed lane, unknown tip, unmigrated mission, existing mission branch) name the blocking object (WP id, SHA, path, branch, or mission) and a remedy command. | Usability | High | Open |
| NFR-005 | Quality gates | New and changed code passes `ruff check`, `ruff format --check`, and `mypy --strict` with zero issues; cyclomatic complexity ≤ 15 per function; diff coverage ≥ 90%. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Binding decision | Implement the #5100 operator decision (comment 5870360497, option E) as written; do not relitigate it. | Business | High | Open |
| C-002 | Single protection authority | "Protected target" and the commit-to-target override are resolved only through `ProtectionPolicy` (extended with one primary-or-configured query); no second protection check, no forge API. | Technical | High | Open |
| C-003 | No runtime fallback | No code path reinterprets a mission's topology from its artifacts at runtime; drift is fixed by migration and reported by doctor. | Technical | High | Open |
| C-004 | Coord topologies unchanged | `coord` and `lanes_with_coord` behaviour is out of scope and must not change. | Technical | High | Open |
| C-005 | Sibling-owned surfaces | Edits to `consolidation/*` and `tests/integration/**` stay minimal and are called out in the PR; no edits to `tests/specify_cli/**` goldens beyond what this change requires. | Business | High | Open |
| C-006 | PR #5009 coordination | Do not push to PR #5009's branch; absorb only its resolver arm with co-author credit, keyed on topology rather than `effective_root`. | Business | High | Open |
| C-007 | Targeted tests only | Run the named targeted tests and specific architectural gate files only; no full-directory heavy suites (`NO_FULL_HEAVY_SUITES_IN_MISSION`). | Technical | High | Open |
| C-008 | Red-first regressions | Each issue-pinned acceptance test is committed RED, through the real CLI, before its fix (ADR 2026-07-17-1). | Technical | High | Open |
| C-009 | Terminology canon | Mission, not feature; name the sense of "primary", "merge", and "routing"; `repository root checkout`, never "main repository". | Business | High | Open |
| C-010 | User customisation preservation | No foreign git hook or user file is overwritten, deleted, or rewritten (charter: User Customization Preservation). | Technical | High | Open |

### Key Entities

- **Mission metadata (`meta.json`)**: gains `commit_to_target` (absent by default) and `mission_branch` (only for protected-target single_branch missions); `topology` stays the single authority.
- **Lane manifest (`lanes.json`)**: for single_branch holds exactly one repo-root lane.
- **Lane work-tip record**: the recorded last commit of each lane branch, kept independently of the lane branch, worktree, and workspace record.
- **Workspace record (per lane)**: written only by the lane allocator.
- **Status event**: carries the execution-mode stamp (`worktree` / `direct_repo`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A two-WP single_branch mission runs finalize → implement WP01 → for_review with zero `.worktrees/*-lane-*` directories, zero undeclared branches on an unprotected target, and zero `--force` flags, while the `lanes` control on the same fixture creates exactly one lane worktree. — [build] · no-op passable: no
- **SC-002**: A destroyed in-flight lane with one committed change is refused 100% of the time with the recorded tip named, while absorbed (ancestor, squash, or no-work) lanes re-open 100% of the time. — [build] · no-op passable: no
- **SC-003**: After upgrade, all single_branch missions in this repository whose manifest has code lanes (64 at mission start) are re-stamped `lanes` in a dedicated data commit, and the doctor reports 0 remaining. — [build] · no-op passable: no
- **SC-004**: A planning_artifact WP with a deliverable reaches for_review with zero `--force` on a non-`main` target, and one without a deliverable is refused. — [build] · no-op passable: no
- **SC-005**: A mission created on a non-primary branch without `--topology` is `lanes` in 100% of the covered branch/pr-bound combinations. — [build] · no-op passable: no

## Assumptions

- **Write checkout.** The decision's "repo-root checkout" (item 1) is read as the mission's write checkout. That is either the repository root checkout or a validated owned checkout (ADR 2026-09-03-1, PR #5009). The owned-checkout lifecycle is kept.
- **Protected target.** A target counts as protected when it is the primary branch or when `ProtectionPolicy` reports it protected. This is exactly the decision's "primary plus configured" rule, exposed as one query on the existing authority.
- **Mission-branch timing.** The mission branch is minted at `mission create`, not at first implement. Protected targets refuse planning commits, so a mission branch that did not exist until implement could never receive the spec, plan or tasks. The decision's semantics are unchanged: one write surface, no worktree, a dirty-checkout refusal at implement, and consolidate landing the branch on the target.
- **`--pr-bound` with unreachable coordination.** This arm also defaults to `lanes`, because the decision says `single_branch` only comes from explicit requests. This answers #2602.
- **Override flag.** It is named `--commit-to-target` and persisted as `meta.json` `commit_to_target: true`. It is absent by default.
- **Where tips are recorded.** The tip is recorded outside the workspace record so that it survives context cleanup and so that git's garbage collection cannot drop the stranded commits. This departs from the brief's "persist in the workspace record" wording, for the reasons in the plan. The recording mechanism is also chosen in the plan.
