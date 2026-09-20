# Mission Specification: Merge/Git Destructive-Operation Safety

**Mission Branch**: `fix/merge-destructive-op-safety`
**Created**: 2026-09-19
**Status**: Draft
**Input**: Bug trio #4752, #4753, #4754 — `spec-kitty merge` / `merge --abort` fire destructive git commands with no dirty/branch/state guard, silently destroying uncommitted operator work.

## Overview

`spec-kitty merge` and `spec-kitty merge --abort` run irreversible git commands
(`reset --hard`, `worktree remove --force`, `merge --abort`) against the
operator's **primary checkout** and **lane worktrees** without first verifying it
is safe to do so. Each can silently delete uncommitted work and still exit `0`
with a success line. A grounding squad confirmed all three defects are live on
current `main` (`ba4e590142`), unchanged since the `29507866f` (4.0.0rc4) repro
baseline, and that the codebase has **~9 forked dirty-state predicates with no
canonical "refuse-before-destroy" owner** — so the fix unifies one guard rather
than patching three sites (Decision `guard_strategy`). Two coupled same-seam
surfaces (coord-worktree teardown, orchestrator-api cleanup mirror) are folded
in; standalone `git branch -D` unmerged-commit loss is deferred as a distinct
follow-up (Decision `adjacent_surface_scope`).

**Governing design decision (from the post-spec adversarial point-cut):** every
guard is a **pre-mutation preflight** — all dirty/branch checks (primary checkout,
lane worktrees, coord worktree) run *before* the target ref is advanced and before
any destructive command. On any unsafe condition the merge **refuses fail-closed**
before mutating anything. This makes atomicity uniform (no post-hoc restore, no
partial ref advance, no half-torn coordination triple) and is the shape all
Functional Requirements below assume.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Merge never destroys uncommitted work in the primary checkout (Priority: P0)

An operator has a mission ready to merge. Their repository-root checkout happens
to be on a different branch (`feature-x`) with an uncommitted edit to a tracked
file. They run `spec-kitty merge`. Today, after advancing the target ref, the
merge runs `git reset --hard HEAD` on that checkout, destroying the edit, then
crashes mid-bookkeeping with a raw `SafeCommitHeadMismatch` traceback — leaving
the target advanced but bookkeeping uncommitted. (#4752)

**Why this priority**: Silent, unrecoverable loss of tracked work plus a
half-completed merge. Data/state corruption → P0 in the triage guide.

**Independent Test**: With a real git repo and a mission staged to merge, put the
primary checkout on a non-target branch with an uncommitted tracked edit; run the
lane-based merge; assert the merge **refuses before any mutation** with an
actionable message and the edit survives.

**Acceptance Scenarios**:

1. **Given** the primary checkout is on a branch other than the target branch,
   **When** `spec-kitty merge` runs, **Then** it refuses in preflight before
   advancing any ref or resetting anything, names the current vs expected branch,
   and exits non-zero with no work destroyed.
2. **Given** the primary checkout is on the target branch but has uncommitted
   tracked changes, **When** `spec-kitty merge` runs, **Then** it refuses in
   preflight before any `reset --hard` and preserves those changes.
3. **Given** the primary checkout is on the target branch and clean, **When**
   `spec-kitty merge` runs, **Then** the merge completes exactly as it does today
   (no behavior change on the safe path).
4. **Given** an off-target or dirty primary checkout, **When** `spec-kitty merge
   --resume` runs, **Then** the same preflight guard refuses identically to a
   fresh merge.

---

### User Story 2 - Merge never deletes uncommitted work in a lane or coord worktree (Priority: P0)

An implementer left uncommitted changes (and untracked files) in a lane worktree
— work never committed to the lane branch. The operator merges the mission.
Today lane cleanup runs `git worktree remove <path> --force`, deleting that work
with a "Removed worktree" success line and exit `0`; the work was never in the
merged branch, so it is unrecoverable. (#4753)

**Why this priority**: Unrecoverable loss of implementation work with false
success. Data loss → P0.

**Independent Test**: Seed a lane worktree with uncommitted tracked changes and
an untracked file; run the merge; assert the worktree is detected dirty in
preflight and **not** force-removed — the merge refuses fail-closed (no
retention flag) or the worktree is retained (retention flag set) — and the work
survives in both cases.

**Acceptance Scenarios**:

1. **Given** a lane worktree with uncommitted tracked changes or untracked files
   and no retention flag in effect, **When** `spec-kitty merge` runs, **Then**
   preflight detects the dirty worktree before any ref advance, the merge refuses
   fail-closed with remediation, exits non-zero, and the work survives (repo
   byte-identical to pre-invocation).
2. **Given** the same dirty lane worktree **and** worktree retention in effect
   (`--keep-worktree` / `retain_worktrees`), **When** `spec-kitty merge` runs,
   **Then** the worktree is retained (never `--force`-removed), the dirty work
   survives, and the merge does not print an unqualified success line for that
   worktree.
3. **Given** a clean lane worktree, **When** merge cleanup runs, **Then** it is
   removed exactly as today (exit 0, unchanged messaging).
4. **Given** a dirty coordination worktree, **When** `spec-kitty merge` runs,
   **Then** the same preflight guard applies; and because the coordination triple
   (branch + worktree + marker) is one coupled teardown decision, a guard refusal
   holds back the coupled coord-branch deletion and marker teardown too — the
   triple is retained atomically, with no half-torn coord state.

---

### User Story 3 - `merge --abort` only touches spec-kitty's own merge state (Priority: P1)

An operator is resolving their **own** hand-run `git merge` conflict in the
primary checkout (30 minutes of manual resolution, `MERGE_HEAD` present). There is
no active spec-kitty merge. They run `spec-kitty merge --abort` (e.g. to clear
stale spec-kitty state). Today it prints "No active merge state to abort." and
then runs `git merge --abort` on their checkout anyway, destroying their
resolution, exit `0`. (#4754)

**Why this priority**: Loss of manual conflict resolution with a contradictory
success line. Real but narrower blast radius than the P0s → P1.

**Independent Test**: Create a repo with a genuine in-progress user merge
(`MERGE_HEAD` in the primary checkout) and **no** spec-kitty merge state; run
`spec-kitty merge --abort`; assert the user's `MERGE_HEAD` and resolution are
untouched.

**Acceptance Scenarios**:

1. **Given** no active spec-kitty merge state and a user's own `MERGE_HEAD` in the
   primary checkout, **When** `spec-kitty merge --abort` runs, **Then** it does
   not run `git merge --abort` on the primary checkout and the user's in-progress
   merge is preserved.
2. **Given** active spec-kitty merge state, **When** `spec-kitty merge --abort`
   runs, **Then** it clears spec-kitty-owned state (runtime dir, lock, workspace)
   as today and its messaging is internally consistent (no "nothing to abort"
   followed by an abort).

### Edge Cases

- **Residue honesty.** Toolchain/bookkeeping churn (specifically the VCS-lock
  stamp inside `meta.json`) must NOT be treated as "dirty" and must NOT block a
  safe merge — the guard honors the same residue classifier the existing gates use
  (`is_toolchain_generated_churn`), or it introduces a false-positive regression
  in the opposite direction.
- **Atomic refusal.** A refusal is pre-mutation: no ref advance, no destructive op,
  and no partial coordination teardown has executed before the guard fires.
- **`--resume` parity.** `merge --resume` honors every guard identically to a fresh
  merge.
- **Scratch workspace excluded.** The internal merge scratch worktree
  (`.kittify/runtime/merge/<id>/workspace`, `cleanup_merge_workspace`) is out of
  guard scope and always cleans up unconditionally; the guard applies only to
  user-facing lane and coordination worktrees.
- **Explicit discard excluded.** `mission close --discard` is intentional
  destruction and is out of scope — the guard blocks *unintended* destruction, not
  an operator's explicit discard.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Refuse merge when primary checkout is off-target | As an operator, I want `spec-kitty merge` to refuse in preflight (before any mutation) when my repository-root checkout is not on the target branch, so my unrelated work is never reset. | High | Open |
| FR-002 | Refuse merge when primary checkout is dirty | As an operator, I want `spec-kitty merge` to refuse in preflight (before any `reset --hard`) when the target-branch primary checkout has uncommitted tracked changes, so those changes survive. | High | Open |
| FR-003 | Preflight-detect dirty lane worktrees, fail-closed | As an implementer, I want merge preflight to detect a dirty lane worktree before any ref advance and — absent worktree retention — refuse the merge fail-closed rather than ever `--force`-removing it, so uncommitted work never on the lane branch is not deleted. | High | Open |
| FR-004 | Coupled coord-triple retention on refusal | As an operator, I want a dirty coordination worktree to trigger the same preflight guard, and a refusal to hold back the whole coupled coord teardown (branch + worktree + marker) as one atomic decision, so the coordination triple is never half-torn. | High | Open |
| FR-005 | Scope `merge --abort` to spec-kitty state | As an operator, I want `spec-kitty merge --abort` to abort a git merge only when active spec-kitty merge state exists (and only within spec-kitty-owned scope), so my own in-progress merge is never aborted. | High | Open |
| FR-006 | Actionable refusal + honest exit | As an operator, I want every guard refusal to print the concrete condition and remediation and exit non-zero, the retain path to avoid an unqualified success line for a retained dirty worktree, and no two success lines to contradict each other, so I can trust the CLI's report. | Medium | Open |
| FR-007 | Unified refuse-before-destroy guard | As a maintainer, I want the branch/dirty checks routed through one shared guard primitive (not re-implemented per site) and worktree removal routed through the single `remove_workspace` chokepoint, so this defect class is closed by construction and future destructive sites reuse it. | High | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Pre-mutation atomic refusal | All guards run in pre-merge preflight; on any refusal, the destructive call site is never reached (proven by a spy/mock asserting call ordering) and repo state is byte-identical to pre-invocation. | Reliability | High | Open |
| NFR-002 | No safe-path regression + resume parity | The clean/on-target merge, the `--resume` merge, and the abort path behave identically to pre-change on safe inputs; ≥1 regression test per path (including `--resume`) proves parity. | Reliability | High | Open |
| NFR-003 | Residue false-positive rate zero | A `meta.json` whose only diff is the VCS-lock stamp (the concrete residue fixture) never triggers a guard refusal; the injected residue classifier is exercised by a targeted test. | Correctness | High | Open |
| NFR-004 | Red-first coverage | Each of #4752/#4753/#4754 ships an issue-pinned `@pytest.mark.regression` test that is RED on the base commit and GREEN after the fix, through the pre-existing entry point. | Testability | High | Open |
| NFR-005 | Complexity ceiling | New/changed functions stay ≤15 cyclomatic complexity; new branches/helpers carry focused tests in the same commit. | Maintainability | Medium | Open |
| NFR-006 | Unification enforced by test | An architectural/routed-call test asserts the in-scope destructive commands (`reset --hard`, `worktree remove --force`, `git merge --abort`) execute ONLY behind the guard / `remove_workspace` chokepoint, and that no new parallel dirty predicate is introduced alongside `_dirty_entries`. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Reuse canonical building blocks | The guard reuses the existing residue-aware dirty check (`git/ref_advance._dirty_entries`) and on-target assertion (`merge/preflight._enforce_planning_artifact_target_branch`) rather than adding a new parallel dirty predicate. | Technical | High | Open |
| C-002 | Do not overload `SafeCommitHeadMismatch` | Introduce a new typed refusal (modeled on `RefAdvanceDirtyWorktreeError`); do not repurpose the commit-time mismatch exception, whose downstream catchers must not change semantics. | Technical | High | Open |
| C-003 | Worktree-removal chokepoint | Route the LIVE user-facing worktree force-removals (executor lane cleanup, coordination teardown + stale-prune, orchestrator-api cleanup) through ONE shared `guarded_worktree_remove` seam so the guard lands in one place. Note: `core/vcs/git.py remove_workspace` is a dead adapter (zero callers) and is NOT the chokepoint — the seam is a new helper the live inline destroys call. | Technical | High | Open |
| C-004 | Defer STANDALONE `branch -D` loss | Standalone `git branch -D` unmerged-COMMIT loss (executor/orchestrator/mission_creation, deleting a branch whose commits are unmerged) is out of scope — distinct loss surface, distinct guard (is-branch-merged); note as a follow-up in the PR. The coord-branch deletion **coupled to** a guarded worktree teardown (FR-004) IS in scope and refuses with it. | Technical | Medium | Open |
| C-005 | Classifier injection is the mechanism | `_dirty_entries` already accepts an injectable churn classifier; the fix passes `coordination.coherence.is_toolchain_generated_churn` into the git-layer guard (one classifier, injected — not a second layer), preserving git-plumbing purity (no `specify_cli` import in `git/`). | Technical | Medium | Open |
| C-006 | Scratch workspace out of scope | The internal merge scratch worktree (`cleanup_merge_workspace`) is never guarded and always cleans unconditionally, even if routed near the `remove_workspace` seam. | Technical | Medium | Open |

### Key Entities

- **Primary checkout**: the repository-root checkout where the operator stands; the
  `reset --hard` and `merge --abort` targets.
- **Lane worktree**: a per-lane execution worktree under `.worktrees/`; may hold
  uncommitted work never on the lane branch.
- **Coordination triple**: the coord branch + coord worktree + marker, torn down as
  one coupled decision (CLAUDE.md #3131).
- **Refuse-before-destroy guard**: the unified preflight primitive asserting
  (HEAD-on-target and/or worktree-clean, residue-aware) and raising a typed refusal
  before any destructive op.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 0 of the three documented reproductions destroy uncommitted work after the fix (each proven by a red→green regression test).
- **SC-002**: 100% of guard refusals are pre-mutation — the destructive call site is never reached on the refusal path and post-refusal repository state is byte-identical to pre-invocation (asserted in tests).
- **SC-003**: 0 behavior change on the clean/on-target merge, `--resume`, and abort safe paths (parity tests pass).
- **SC-004**: 1 shared guard primitive covers all in-scope destructive sites, enforced by the NFR-006 architectural test (no new parallel dirty predicate).
