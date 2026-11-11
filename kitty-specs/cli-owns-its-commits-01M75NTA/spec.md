# Mission Specification: The CLI commits its own writes; dirty gates are Mission-scoped

**Mission Branch**: `fix/7545-cli-owns-its-commits` (single_branch, target `fix/7545-cli-owns-its-commits`)
**Created**: 2026-11-11
**Status**: Draft
**Input**: Sub-epic #7545 (parent epic #7543); issues #7556, #7555, #5938, #3933. Context only: #5744, #5905, #5515, #5101, #2017, #7510.

## Intent Summary

Brief-intake mode: the dispatch brief for #7545 (scope, slices, non-goals, test policy) is
comprehensive, so no discovery questions were needed. The operator was not present (cloud
dispatch). The three judgement calls are recorded as resolved Decision Moments
(`decisions/DM-01M75NY1Q2F35PYMESZB0S5DWN.md`, `DM-01M75NY6CET5GK3CZ4QEEBJXGC.md`,
`DM-01M75NYB0GQSB8G62TD9W53KC6.md`), and the pull request flags them for review.

- **Primary actor:** an agent or operator driving a Mission through the documented
  `spec-kitty` commands (in the benchmark: a harness running `init`, `next`, `implement`,
  `move-task`, `setup-plan`, `record-analysis`, `accept`, `consolidate`).
- **Trigger:** a spec-kitty command writes a tracked file, or a later command checks the
  working tree before it writes.
- **Desired outcome:** the agent never has to hand-commit a file spec-kitty wrote, and a gate
  never refuses because of another Mission's files.
- **Rule that must always hold:** spec-kitty never commits a file the operator edited (#5905),
  never commits onto a protected branch without the capability that flow already holds, and a
  gate still refuses on uncommitted work that the guarded write would mix with.
- **Evidence:** the rc7 benchmark register (23 guaranteed first-attempt failures and about 70
  hand commits over six runs) and seven Mission tracers.

## Domain Language

| Term | Meaning here | Avoid |
|---|---|---|
| **Mission-scoped dirt** | an uncommitted path classified by whose it is: this Mission's own directory, another Mission's directory, or outside every Mission | "dirty tree" for the whole checkout when only one class matters |
| **Own write** | a tracked file the running command itself wrote during this invocation | "residue" (overloaded; see `docs/context/orchestration.md#residue`) |
| **Operator edit** | a path that was already dirty before the command ran, or that the command did not write | "user data" |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Another Mission's files never block this Mission (Priority: P1)

An agent works on Mission A in a checkout that also holds untracked files from Mission B
(a stale matrix, a decisions directory, a half-written spec). Today `record-analysis` refuses
with `DIRTY_WORKTREE` and the single_branch `implement` claim refuses with
`WRITE_CHECKOUT_DIRTY`, so the agent stashes, moves or excludes Mission B's files.

**Why this priority**: four Mission tracers hit it; the workarounds (moving `kitty-ops/`,
`git stash -u`) have mass-deleted tracked files.

**Independent Test**: create two Missions in one repository, leave an untracked file in
Mission B's directory, run `record-analysis` and the single_branch claim for Mission A.

**Acceptance Scenarios**:

1. **Given** an untracked file under another Mission's directory, **When** `record-analysis`
   runs for this Mission, **Then** it records the report and names that path in a warning.
2. **Given** an uncommitted edit inside this Mission's own directory, **When**
   `record-analysis` runs, **Then** it still refuses with `DIRTY_WORKTREE` naming that path.
3. **Given** a single_branch Mission and another Mission's untracked directory in the write
   checkout, **When** `implement WP01` claims, **Then** the claim succeeds and warns, naming it.
4. **Given** an uncommitted operator edit to a code file in that write checkout, **When**
   `implement WP01` claims, **Then** it still refuses with `WRITE_CHECKOUT_DIRTY`.

### User Story 2 - A `next`-driven coordination Mission consolidates (Priority: P1)

An agent drives a coordination-topology Mission through `spec-kitty next`. Each call appends
to `mission-events.jsonl` in the coordination worktree and leaves it untracked, so
`consolidate` refuses `MERGE_UNSAFE_WORKTREE_DIRTY` (#5938).

**Independent Test**: create a coordination Mission, run one `next --result success`, then
inspect the coordination worktree.

**Acceptance Scenarios**:

1. **Given** a coordination Mission, **When** `next` records its invocation, **Then** the
   coordination worktree is clean afterwards and the row is on the coordination branch.
2. **Given** a coordination worktree with the operator's own uncommitted edit, **When** `next`
   runs, **Then** that edit stays uncommitted.

### User Story 3 - `setup-plan` and `move-task` commit everything they write (Priority: P2)

`setup-plan` commits `plan.md` but leaves the PlanCompleted event it appends right after
uncommitted; `move-task` with auto-commit leaves part of a transition uncommitted (#3933).

**Acceptance Scenarios**:

1. **Given** a substantive `plan.md`, **When** `setup-plan` runs with auto-commit, **Then**
   the plan and the PlanCompleted event land in one commit and the JSON reports that
   commit's hash.
2. **Given** a single_branch Mission with auto-commit on, **When** `move-task` moves a WP
   (with or without `--note`), **Then** no file the command wrote is left uncommitted.

### User Story 4 - `init` commits what it wrote (Priority: P2)

`spec-kitty init` inside a git repository writes `.kittify/`, `AGENTS.md`, `.gitignore` and
`.gitattributes` and commits none of them (#7555), so the first gated command sees them as
dirt.

**Acceptance Scenarios**:

1. **Given** a git repository, **When** `init` runs, **Then** everything it wrote lands in
   one commit attributed to spec-kitty, and the tree is clean.
2. **Given** a file that was already uncommitted before `init`, **When** `init` runs, **Then**
   that file stays uncommitted (even if `init` also touched it).
3. **Given** `--no-commit`, **When** `init` runs, **Then** nothing is committed.
4. **Given** a directory that is not a git repository, **When** `init` runs, **Then** it
   behaves as today (no commit, the "run git init" step is shown).

### Edge Cases

- A wholly untracked other Mission is reported by git as one collapsed `kitty-specs/<other>/`
  entry; it must classify as another Mission's path.
- A path under `kitty-specs/` that is not inside any Mission directory (for example a stray
  `kitty-specs/README.md`) counts as outside every Mission.
- The Mission's own directory may have aliases (the composed `<slug>-<mid8>` directory);
  those count as this Mission.
- A commit refused by protected-branch policy leaves the file uncommitted and reports why;
  it never fails the command that wrote it.
- `init` on an unborn branch (fresh `git init`, no commits yet) still commits.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | One Mission-scoped dirt predicate | As a gate author, I want one shared rule that classifies an uncommitted path as this Mission's, another Mission's, or outside every Mission (collapsed directories and Mission directory aliases included) so that every gate scopes dirt the same way. | High | Open | [build] | no — unit tests pin each class, including the collapsed-directory shape the existing private rule misclassifies |
| FR-002 | record-analysis refuses only on its own Mission | As an agent, I want `record-analysis` to refuse only on this Mission's own uncommitted paths and to warn, naming them, about every other dirty path so that other Missions' residue no longer blocks it. | High | Open | [build] | no — paired with the same-fixture control that an own-Mission edit still refuses |
| FR-003 | The single_branch claim ignores other Missions | As an agent, I want the single_branch `implement` claim to warn about, not refuse on, another Mission's paths, while still refusing on uncommitted code and on this Mission's own non-bookkeeping files. | High | Open | [build] | no — paired with the same-fixture control that a code edit still refuses |
| FR-004 | `next` commits its coordination event row | As an agent driving `next`, I want the `mission-events.jsonl` row `next` writes into the coordination worktree committed there, so that `consolidate` does not refuse on it. | High | Open | [build] | no — the reproduction asserts a clean coordination worktree after `next` |
| FR-005 | setup-plan commits its PlanCompleted event | As an agent, I want `setup-plan` to commit the PlanCompleted event together with `plan.md` and report the hash of the commit it made, so that no plan-phase write is left dirty. | Medium | Open | [build] | no — asserts a clean tree and a non-null hash after the command |
| FR-006 | move-task leaves none of its writes uncommitted | As an agent, I want `move-task` with auto-commit to commit every tracked file it wrote on a single_branch Mission, so that the next gate does not refuse on it. | Medium | Open | [build] | no — asserts a clean tree after the transition |
| FR-007 | init commits its own writes | As a new user, I want `init` inside a git repository to commit everything it wrote in one attributed commit, leaving files that were dirty before it ran untouched, with `--no-commit` to opt out. | Medium | Open | [build] | no — asserts the commit's file set and a clean tree; the `--no-commit` arm asserts no commit |
| FR-008 | Existing refusals keep refusing | As a maintainer, I want every gate this mission touches to keep refusing on the dirt it guarded before when that dirt belongs to this Mission or would be mixed into its commit. | High | Open | [ratchet] | no — the existing refusal tests stay green, re-pinned only where #7556 changes the expected class |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No extra git round-trips in gates | The Mission-scoped classification adds zero `git` subprocess calls to a gate (it classifies the paths the gate already listed). | Performance | High | Open |
| NFR-002 | Code quality | New and changed code passes `ruff check`, `ruff format --check`, and `mypy` with zero new findings; every new function has cyclomatic complexity ≤ 15. | Maintainability | High | Open |
| NFR-003 | Coverage | Every new branch is executed by a focused test in this mission (diff coverage ≥ 90%). | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Never sweep operator edits | No new commit stages a path that was dirty before the command ran or that the command did not write (#5905). | Technical | High | Open |
| C-002 | Protected-branch policy unchanged | No new protected-branch capability holder and no bypass; a refused commit is reported, not forced. | Technical | High | Open |
| C-003 | Commits through the canonical seams | New commits go through `safe_commit` or the commit router; no raw `git commit` / `git add` in new code; no new `git status` argv outside `kernel.git`. | Technical | High | Open |
| C-004 | No path exemptions by name | No gate gains a new filename exemption; scoping is structural (whose Mission a path belongs to). `mission-events.jsonl` stays real dirt (#5669 ruling). | Technical | High | Open |
| C-005 | No new size or ratchet gates; no pack edits | No new architectural ratchet; prompt or template wording changes go to `spec-kitty-open-packs`, not `packs/built-in/`. | Technical | Medium | Open |
| C-006 | Build on PR #7557 | Do not duplicate #7557's lifecycle-record bookkeeping rule; this mission does not touch `is_self_bookkeeping_churn`. | Technical | Medium | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the #5938 reproduction (one `next` call, then the ordinary lifecycle), `consolidate` lands with exit 0 instead of refusing. — [build] · no-op passable: no
- **SC-002**: Driving this mission end to end needs no hand commit of a file a gated command then refused on because of another Mission's files (recorded in the tooling-friction tracer). — [build] · no-op passable: no
- **SC-003**: After `init`, `setup-plan`, `move-task` and `next` (coordination worktree), `git status` shows none of the files those commands wrote. — [build] · no-op passable: no
- **SC-004**: Every refusal test that existed before this mission still passes, or is re-pinned with a stated reason. — [ratchet] · no-op passable: yes — it is a regression guard, paired with SC-001..003

## Assumptions

- PR #7557 lands independently; the `kitty-ops/lifecycle/` half of the `next` dirt is its job.
- `next` writing into the repository root checkout (single_branch / lanes) stays as it is:
  the claim gate already exempts this Mission's own log there (Decision Moment
  `01M75NYB0GQSB8G62TD9W53KC6`).
- Stretch items #5515 (surface git's stderr from `safe_commit`) and #5744 (`base_commit`
  write vs the lane guard) are done only if slice 1 covers them without widening scope;
  otherwise they stay `Refs`.
