# Mission Specification: Destructive ops never delete the only copy

**Mission Branch**: `fix/5965-5966-destructive-residue-context`
**Created**: 2026-10-10
**Status**: Draft
**Input**: Issues #5965 and #5966, plus the pre-spec research squad findings (all defects live on `main` at `f810b924a9`).

## Intent Summary

- **Primary actor**: an operator or agent running `spec-kitty consolidate`, or `spec-kitty consolidate --abort`, on a Mission.
- **Trigger**: the run cleans a checkout up: it removes the coordination worktree, or resets a checkout back to a branch tip.
- **Problem today**: the cleanup decides which uncommitted files are disposable tool clutter without knowing which Mission or which checkout it is looking at. It deletes a reviewer's uncommitted rejection feedback, hand-written `traces/` notes, or another Mission's in-progress edits, and still reports success.
- **Desired outcome**: cleanup removes only real tool clutter. When the only copy of someone's work is in the way, it refuses, names the files, and the run fails.
- **Invariant**: a file whose only copy is in the checkout being cleaned, or that belongs to a different Mission, is never treated as disposable.
- **Scope decision (operator, 2026-10-10)**: every raw destructive git call in the product is routed through the destructive guard in this Mission. There is no shrink-only ledger of tolerated call sites: such ledgers persist as standing debt. The gate also covers recursive directory deletion of a git checkout.
- **Teardown decision (operator, 2026-10-10)**: when coordination teardown refuses after the lanes already landed, the verified landing stays, the coordination branch, worktree and marker are kept together, the branch delete is skipped, and the run exits non-zero with its own refusal code. `consolidate --resume` finishes the teardown once the operator has committed or moved the files.
- **Root cause, precisely**: the coordination teardown passes the Mission but not the topology, so the classifier falls back to its coordination-projecting default and judges coordination files as a stale copy of the primary partition. The rollback resync passes neither. Whether a coordination-kind file is disposable depends on the checkout it sits in: it is authoritative in the coordination worktree and can be a stale copy only in the repository root checkout.

## Domain Language

| Term | Meaning | Avoid |
|------|---------|-------|
| Disposable residue | An uncommitted file a cleanup may discard because an authoritative copy exists elsewhere or the toolchain regenerates it | "clutter", "churn" as a decision word |
| Only copy | An uncommitted file that exists in no other checkout or commit | — |
| Checkout role | Which checkout a cleanup acts on: repository root checkout, coordination worktree, mission worktree, lane worktree | "primary" without a sense (see `docs/context/orchestration.md`) |
| Destructive operation | An operation that can discard uncommitted work or unmerged commits: `git reset --hard`, `git worktree remove --force`, `git worktree prune`, `git branch -D`, `git checkout --force`, `git clean -f`, `git stash drop`, and recursive deletion of a directory inside a git checkout | — |
| Destructive guard | The single owner that checks a checkout before a destructive git operation runs | — |

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Rejection feedback survives consolidate (Priority: P1)

A reviewer rejects a work package with `move-task --to planned --no-auto-commit`, so the review-cycle file and their `traces/` notes stay uncommitted in the coordination worktree. The operator later runs `consolidate`.

**Why this priority**: this is #5965. The reviewer's feedback exists nowhere else, and losing it silently breaks the rework loop.

**Independent Test**: on a coordination-topology Mission, reject a work package through the real `move-task --to planned --no-auto-commit` (which decides where the review-cycle file lands), add a `traces/` note, then run the real `consolidate` entry point and check the files, the exit code, the target branch and the coordination branch.

**Acceptance Scenarios**:

1. **Given** uncommitted review-cycle, `traces/` or acceptance-matrix files in the coordination worktree, **When** `consolidate` reaches coordination teardown, **Then** the worktree, coordination branch and marker are all kept, the files are intact, the verified landing on the target is not rolled back, and the run exits non-zero with its own refusal code, naming the files and the remedy (commit or move them, then `consolidate --resume`).
2. **Given** that refusal and the operator has committed the files on the coordination branch, **When** they run `consolidate --resume`, **Then** teardown completes without a false refusal for the coordination branch having moved.
3. **Given** only regenerated tool output is uncommitted in the coordination worktree, **When** `consolidate` reaches teardown, **Then** teardown proceeds as it does today.
4. **Given** the same uncommitted files, **When** `consolidate --abort` or `orchestrator-api consolidate-mission` tears the coordination worktree down, **Then** the same refusal applies.

### User Story 2 - Abort leaves other Missions' edits alone (Priority: P1)

While Mission A's consolidation is aborted, Mission B has uncommitted review-cycle and `traces/` edits in the repository root checkout.

**Why this priority**: this is #5966. `--abort` says "nothing is lost" while it destroys another Mission's work.

**Independent Test**: two Missions in one repository (a `lanes` Mission being consolidated and a second Mission with uncommitted edits), run `consolidate --abort` through the real entry point, and check Mission B's files.

**Acceptance Scenarios**:

1. **Given** Mission B has uncommitted review-cycle or `traces/` files in the repository root checkout, **When** Mission A's `consolidate --abort` resyncs that checkout, **Then** the resync refuses with a message naming Mission B's files, and they are intact.
2. **Given** Mission A's own stale status copy is the only uncommitted file, **When** `--abort` resyncs, **Then** it is cleaned up as today.

### User Story 3 - No new unguarded destructive commands (Priority: P2)

A contributor adds code that runs `git reset --hard` directly.

**Why this priority**: this bug family has recurred about a dozen times because each destructive call site decides for itself. A gate stops the next one.

**Independent Test**: the architectural test fails on a fixture module that runs a raw destructive git command, and passes on the product tree.

**Acceptance Scenarios**:

1. **Given** a module outside the destructive guard that builds a destructive git argv or recursively deletes a git checkout directory, **When** the architectural test runs, **Then** it fails and names the module and line.
2. **Given** the product tree after this Mission, **When** the test runs, **Then** it passes with an allowlist holding only the guard itself and named, tool-owned scratch worktree paths, each with a written reason.

### Edge Cases

- A file in the coordination worktree that has a committed copy on the coordination branch and an identical working copy: not "only copy", but it is also not dirty; nothing changes.
- A Mission whose stored topology cannot be read: the check refuses rather than assuming a topology.
- A caller that cannot name its checkout role: it cannot call the check at all (the arguments are required).
- A destructive op on a scratch worktree the tool itself created under `.kittify/runtime/`: allowed, because no user can have written there.
- A teardown that refused: the coordination branch and worktree are kept, so the operator can recover and re-run.
- A lane worktree that holds uncommitted rework when consolidate removes lanes: the same only-copy rule applies.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Residue check needs full context | As an operator, I want the disposable-residue check to require the Mission, its topology and the checkout role, with no default, so that no caller can get the destructive answer by omission. | High | Open | [build] | no |
| FR-002 | Disposability depends on the checkout | As a reviewer, I want a coordination-partition file (review cycle, traces, acceptance matrix, issue matrix) never treated as disposable inside the coordination worktree, and disposable at most as a stale copy in the repository root checkout, decided by checkout role rather than by filename, so that my uncommitted feedback survives consolidate. | High | Open | [build] | no — paired with the regenerated-output positive control on the same fixture |
| FR-003 | Other Missions' files are kept | As an operator running several Missions, I want files of a different Mission never treated as disposable in any checkout, so that one Mission's cleanup cannot destroy another's work. | High | Open | [build] | no — paired with the own-stale-status positive control |
| FR-004 | Abort resyncs with this run's context | As an operator, I want `consolidate --abort` and the rollback resync to pass this run's Mission, topology and checkout role, so that the resync keeps other Missions' uncommitted edits. | High | Open | [build] | no |
| FR-005a | A refused teardown fails the run without undoing the landing | As an operator, I want a coordination teardown refused over only-copy files to keep the verified landing, keep the coordination branch, worktree and marker together (the branch delete is skipped), and exit non-zero with its own refusal code naming the kept files and the remedy, on `consolidate` and `consolidate --abort`, instead of logging a warning and exiting 0. | High | Open | [build] | no |
| FR-005b | Resume completes a refused teardown | As an operator, I want `consolidate --resume` after a refused teardown, once I have committed or moved the files, to finish the teardown without refusing because the coordination branch moved. | High | Open | [build] | no |
| FR-006 | Gate on destructive operations | As a maintainer, I want an architectural test that fails when a destructive operation (as defined in Domain Language, including recursive deletion of a git checkout directory) is performed outside the destructive guard, so that the bug family cannot recur through a new call site. Its allowlist holds only the guard and named tool-owned scratch paths, each with a reason; there is no ledger of tolerated sites. It lands after FR-007 so it is green on arrival. | High | Open | [build] | no — proven red on a fixture module |
| FR-007 | Route every existing destructive operation through the guard | As an operator, I want every destructive operation in the product (lane allocation and teardown, Mission-type scaffolding, charter pack sources, the VCS adapter, Mission-creation rollback including its worktree prune and directory deletion, the coordination seed, doctor husk cleanup, the coordination workspace's stale-registration removal, consolidation phases and the orchestrator API) to go through the destructive guard, so that each one checks for the only copy of someone's work before it runs. | High | Open | [build] | no |
| FR-009 | Fresh-branch deletion rule | As an operator, I want the guard to allow deleting a branch only when it holds no commit beyond its creation base or its commits are reachable elsewhere, so that a rollback of a just-created branch still works and a branch with unique work is never force-deleted. | Medium | Open | [build] | no |
| FR-008 | Red-first reproductions | As a maintainer, I want an issue-pinned reproduction for #5965 (real `move-task --to planned --no-auto-commit`, then `consolidate`) and for #5966 (two Missions, then `consolidate --abort`) that drives the real entry points and fails before the fix, so that the fix is proven against the reported path. | High | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Normal path unchanged | Every existing consolidation, abort and lane-teardown test that passes on `main` still passes; 0 new refusals on runs whose only uncommitted files are regenerated tool output. | Reliability | High | Open |
| NFR-002 | Refusals are actionable | 100% of new refusals name each kept file (or the first 20 plus a count) and give one recovery command or step. | Usability | High | Open |
| NFR-003 | Code quality gates | All changed functions stay at cyclomatic complexity ≤ 15; ruff, ruff format and mypy report 0 issues on changed files; diff coverage ≥ 90%. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | One owner | The disposable-residue decision keeps one home, next to the coordination/primary partition rule; the destructive guard is the only module that runs destructive git commands. No second classifier is introduced. | Technical | High | Open |
| C-002 | Fail closed | Any missing or unreadable context (topology, Mission, role) refuses rather than deletes. | Technical | High | Open |
| C-003 | Out of scope | Follow-up: #5967 (stale status events over pull), #5968 (rewritten dependency lane) and #3129 (scoped shadow workspaces) are separate work. | Business | High | Open |
| C-004 | Canonical CLI only | No change to the consolidate or orchestrator-api command surface beyond new refusal codes and messages; `orchestrator-api consolidate-mission` never tears down the coordination worktree, so it has no teardown refusal to report (brownfield finding). | Technical | Medium | Open |
| C-005 | No new rollback path | A refused teardown never triggers a rollback of a landing that passed reconciliation; the single rollback authority is unchanged. | Technical | High | Open |

### Key Entities

- **Residue context**: the Mission, its stored topology and the checkout role a destructive op acts on. Required input to the disposable-residue decision.
- **Kept-files refusal**: the outcome when an only-copy file blocks a destructive op: the list of files, the checkout, and the recovery step.
- **Gate allowlist**: the guard module and the tool-owned scratch paths, each with a written reason.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In the #5965 reproduction, 100% of uncommitted review-cycle, `traces/` and matrix files survive `consolidate`, and the run exits non-zero. — [build] · no-op passable: no
- **SC-002**: In the #5966 reproduction, 100% of the second Mission's uncommitted files survive `consolidate --abort`. — [build] · no-op passable: no
- **SC-003**: 0 destructive git commands are built outside the destructive guard and the named scratch-path allowlist. — [build] · no-op passable: no
- **SC-004**: Regenerated tool output is still cleaned up in 100% of the existing tests that cover it. — [ratchet] · no-op passable: yes — paired with SC-001/SC-002 on the same fixtures

## Assumptions

- Review-cycle, `traces/` and acceptance-matrix files are coordination-partition kinds, as the current partition rule classifies them.
- Tool-owned scratch worktrees under `.kittify/runtime/` (merge workspace, mission-number bake, review baseline) are never written by users.
