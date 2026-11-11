# Mission Specification: Coordination doctor scope and decisions runtime lock hygiene

**Mission Branch**: `kitty/mission-doctor-scope-lock-hygiene-01M75NSF`
**Created**: 2026-11-11
**Status**: Draft
**Input**: Dispatch brief for sub-epic #7549 (epic #7543): #7552 and #7498, with #7540 items 4 and 5 as the field report.
**Intake mode**: brief intake (unattended cloud run). The dispatch brief states the goal, slices, non-goals and Done-when;
the one gap it left (what `--fix` does with no Mission named) is Decision Moment `01M75NVX2D22SPCRPWBARSFHPQ`, resolved
from the brief's own text ("requires explicit confirmation (`--all-missions` …)").

## Intent Summary

- **Primary actor:** an operator (or the agent acting for them) repairing one Mission's coordination state, and every
  Spec Kitty command that writes a decision.
- **Trigger:** a Mission's coordination worktree is missing or stale, or a decision command has left its runtime lock on disk.
- **Desired outcome:** `spec-kitty doctor coordination --fix` repairs exactly the Missions the operator named, including a
  Mission that exists only on its Mission branch; the decisions runtime lock never shows up as uncommitted work, is never
  committed, and so never blocks a landing.
- **Invariant:** a repair never mutates a Mission the operator did not name, and nothing ever deletes a lock file a live
  process may hold.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Repair one Mission without touching the others (Priority: P1)

An operator whose Mission lost its coordination worktree runs `spec-kitty doctor coordination --fix --mission <handle>`.
Only that Mission is repaired. Running `--fix` with no Mission named refuses and explains how to name one or how to opt
into a repository-wide repair.

**Why this priority**: In #7540 a repository-wide `--fix` would have flattened 58 unrelated Missions to repair one.

**Independent Test**: A repository with two Missions that both have repairable findings; `--fix --mission A` repairs A and
leaves B byte-identical; `--fix` alone exits non-zero and changes nothing.

**Acceptance Scenarios**:

1. **Given** Missions A and B each have a fixable coordination finding, **When** the operator runs
   `doctor coordination --fix --mission A`, **Then** A is repaired and B's `meta.json`, branches and worktrees are unchanged.
2. **Given** the same repository, **When** the operator runs `doctor coordination --fix` with no Mission named,
   **Then** the command refuses with a named error, names `--mission <handle>` and `--all-missions`, and changes nothing.
3. **Given** the same repository, **When** the operator runs `doctor coordination --fix --all-missions`,
   **Then** every Mission is repaired, as `--fix` did before this Mission.
4. **Given** Mission B has a stranded coordination `done` (a reconcile marker), **When** the operator runs
   `--fix --mission A`, **Then** B's strand is neither reported nor reverted.
5. **Given** both `--mission` and `--all-missions`, **When** the command runs, **Then** it refuses as a usage error and changes nothing.

### User Story 2 - Find a Mission that lives only on its Mission branch (Priority: P1)

A default-topology Mission settled to `lanes_with_coord` keeps its `meta.json` only on its Mission branch. When its
coordination worktree is gone (for example after `consolidate --abort`), the repository root checkout has no copy.
`doctor coordination` (scan and `--mission`) still finds it, reports the missing worktree, and `--fix --mission` materializes it.

**Why this priority**: Without it the one Mission that needs the repair is invisible, which forced an in-process workaround in #7540.

**Independent Test**: A Mission whose `meta.json` exists only on `kitty/mission-<slug>-<mid8>` with no checkout of that
branch: the scan reports `COORDINATION_WORKTREE_MISSING` for it, and `--fix --mission <mid8>` creates the coordination worktree.

**Acceptance Scenarios**:

1. **Given** a Mission present only on its Mission branch and no checkout of that branch, **When** the operator runs
   `doctor coordination`, **Then** the report includes that Mission's missing coordination worktree.
2. **Given** the same Mission, **When** the operator runs `doctor coordination --fix --mission <handle>` with its
   `mission_id`, mid8 or slug, **Then** the coordination worktree is materialized.
3. **Given** a Mission branch that also carries other Missions' directories (inherited from its base), **When** the scan
   runs, **Then** only the Mission whose own branch it is is attributed to that branch.

### User Story 3 - The decisions runtime lock is never dirt and never committed (Priority: P1)

Every decision command keeps `kitty-specs/<mission>/decisions/index.json.lock` on disk by design (release truncates, never
unlinks). Git never lists it as an untracked change in the repository root checkout, a coordination worktree or a lane
worktree, and no Spec Kitty commit (`spec-commit`, `safe-commit`, or any caller of the shared commit helper) ever stages it.

**Why this priority**: A committed lock makes every later landing collide with the local copy ("would be overwritten by
reset --hard"), which blocked the #7540 landing.

**Independent Test**: After a decision command, `git status --porcelain` in each checkout role lists no lock; a
`spec-commit` that names the lock refuses with a named code and commits nothing.

**Acceptance Scenarios**:

1. **Given** a consumer project with no ignore rule for `*.lock`, **When** a decision command runs, **Then** the lock is
   excluded from `git status` in the root checkout and in every linked worktree.
2. **Given** a `spec-commit` (or `safe-commit`) that names the lock among other files, **When** it runs, **Then** it
   refuses before touching the index, names the lock and the code, and nothing is committed.
3. **Given** the owned `agent decision repair-runtime-lock` route, **When** it removes a tracked lock from the index,
   **Then** it still succeeds (an index-only removal is not staging the lock).
4. **Given** a reset that would overwrite an obstructing untracked or ignored file, **When** it refuses, **Then** the
   message also describes the file's git state in words ("untracked" / "ignored by a .gitignore or exclude rule") next
   to git's own `??`/`!!` code, which callers and tests already read.

### Edge Cases

- An ambiguous `--mission` handle still fails closed with `AMBIGUOUS_HANDLE`; an unknown one with `MISSION_NOT_FOUND`.
- A Mission branch that cannot be read (corrupt ref, unreadable blob, malformed `meta.json`) is skipped with a warning
  finding, never a crash, and never repaired.
- A ref-only Mission never gets the `NEVER_CREATED` flatten (there is no `meta.json` file to edit on disk).
- A repository without `.git/info/exclude` (or not a git repository) still lets the decision command run; the exclude is
  best-effort, the commit refusal is the guarantee.
- A lock that some branch already tracks (written before this Mission) is not repaired automatically here; the existing
  owned `repair-runtime-lock` route stays the repair, and no new commit can add one.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | `--fix` needs a named scope | As an operator, I want `doctor coordination --fix` with neither `--mission` nor `--all-missions` to refuse with a named error and mutate nothing, so that a repair never has an accidental repository-wide blast radius. | High | Open | [build] | no — the same fixture with `--all-missions` must repair, so a do-nothing refusal of everything fails |
| FR-002 | `--all-missions` opt-in | As an operator, I want `--fix --all-missions` to keep today's repository-wide repair, so that the capability is not removed. | High | Open | [build] | no — asserts the second Mission was actually repaired |
| FR-003 | `--mission` scopes every fixer | As an operator, I want `--fix --mission A` to report and repair only Mission A, including the stranded-revert check and its fixer, so that Mission B is untouched. | High | Open | [build] | no — paired positive control: A's finding is repaired on the same fixture |
| FR-004 | Conflicting scope flags refuse | As an operator, I want `--mission` together with `--all-missions` to refuse as a usage error, so that the scope is never ambiguous. | Medium | Open | [build] | yes — paired with FR-003's positive control on the same fixture |
| FR-005 | Coordination-worktree-held Missions are scanned | As an operator, I want the scan to include a settled default Mission whose `meta.json` lives only in its coordination worktree, so that its findings are reported. | High | Open | [build] | no — asserts a finding names that Mission |
| FR-006 | Branch-only Missions are discovered | As an operator, I want the scan and `--mission` to find a Mission whose `meta.json` exists only on its own Mission branch with no checkout holding it, so that its missing coordination worktree is reported and repairable. | High | Open | [build] | no — asserts the finding and, under `--fix`, the materialized worktree |
| FR-007 | Branch attribution is exact | As an operator, I want a Mission branch to contribute only the Mission it belongs to (its `meta.json` names that branch), so that inherited Mission directories are not reported twice or misattributed. | Medium | Open | [build] | yes — paired with FR-006 on the same fixture |
| FR-008 | Lock excluded on every topology | As a Spec Kitty user, I want the decisions runtime lock excluded from git status in the repository root checkout, coordination worktrees and lane worktrees, so that no dirty gate sees it. | High | Open | [build] | no — fixture has no `*.lock` ignore rule and asserts the lock is absent from status after a real decision write |
| FR-009 | Lock never staged | As a Spec Kitty user, I want every commit through the shared commit helper (`spec-commit`, `safe-commit`, Mission commits) to refuse a request that would stage the decisions runtime lock, so that no branch ever tracks it. | High | Open | [build] | no — paired positive control: the same command without the lock commits |
| FR-010 | Owned lock repair still works | As an operator, I want `agent decision repair-runtime-lock`'s index-only removal to keep working, so that a lock committed before this Mission can still be untracked. | Medium | Open | [ratchet] | yes — pins existing behaviour; paired with FR-009 on the same helper |
| FR-011 | Readable obstruction label | As an operator, I want a reset refusal to also describe an obstructing file in words ("untracked", or "ignored by a .gitignore or exclude rule") next to git's status code, so that a refusal is not misread. | Low | Open | [build] | no — asserts the words appear; the existing status-code pins stay green |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Discovery cost | Branch-only discovery adds at most one tree listing per local Mission branch plus one blob read per candidate Mission, and none when no Mission branch exists. | Performance | Medium | Open |
| NFR-002 | Exclude cost | Ensuring the lock exclusion reads `info/exclude` at most once per lock acquisition and writes it at most once per clone. | Performance | Low | Open |
| NFR-003 | Code quality | Every new or changed function passes `ruff` and `mypy --strict` with no new suppressions and stays at cyclomatic complexity ≤ 15. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No lock deletion | Nothing in this Mission unlinks or truncates a decisions lock file; kernel lock guarantee G3 (release truncates, never unlinks) is preserved. | Safety | High | Open |
| C-002 | No rollback changes | Consolidation rollback and landing logic are not changed (owned by the #7544 run). | Scope | High | Open |
| C-003 | Read-only without `--fix` | `doctor coordination` without `--fix` mutates nothing, including branch-only discovery. | Safety | High | Open |
| C-004 | Canonical selector | `--mission` resolution keeps the canonical ladder (mission_id → mid8 → slug) and fails closed on ambiguity; no silent fallback. | Architecture | High | Open |
| C-005 | No new ratchets | No new size or allowlist gate; a removed allowlist entry is a drain, not a new gate. | Governance | Medium | Open |

## Success Criteria *(mandatory)*

- **SC-001**: A repair aimed at one Mission changes zero files, branches or worktrees of any other Mission in a
  two-Mission fixture. — [build] · no-op passable: no
- **SC-002**: A Mission whose only copy is on its Mission branch is reported and repaired in one command. — [build] · no-op passable: no
- **SC-003**: After a decision command, zero lock entries appear in `git status` across root, coordination and lane
  checkouts, and zero commits through the shared helper contain the lock. — [build] · no-op passable: no

## Domain Language

| Canonical term | Meaning here | Avoid |
|----------------|--------------|-------|
| Mission | The unit of work (`kitty-specs/<dir>/`) | feature |
| Mission branch | `kitty/mission-<slug>-<mid8>`, the Mission's topic branch | "the mission repo" |
| repository root checkout | The non-worktree checkout | main repo |
| decisions runtime lock | `kitty-specs/<dir>/decisions/index.json.lock`, the sidecar of `decisions/lock.py` | "stale lock" for a lock that may be live |

## Assumptions

- `--fix` without a scope refuses rather than prompts: the CLI runs non-interactively for agents, and a prompt would hang them.
- The lock exclusion goes in the common-dir `info/exclude` (clone-local, never committed) because git honours it for
  every linked worktree; a committed `.gitignore` change is not imposed on consumer projects.
- A lock already tracked on some branch is out of scope for automatic repair (the owned repair route exists).

## Out of Scope

- Removing `--fix`'s repository-wide capability (it stays behind `--all-missions`).
- Consolidation rollback, landing and `consolidate --abort` behaviour (#7544, #7540 items 1–3).
- The CLI committing its own bookkeeping writes (#7545 / PR #7557).
