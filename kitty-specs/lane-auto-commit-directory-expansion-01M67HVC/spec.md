# Mission Specification: Lane auto-commit takes exact paths, never a collapsed directory

**Mission Branch**: `issue-6750-lane-auto-commit-directory-expansion`
**Created**: 2026-10-30
**Status**: Draft
**Input**: User description: "spec-kitty/spec-kitty#6750 — lane auto-commit passes collapsed directories to `safe_commit`, lands children then falsely blames a hook"

## Intent Summary

- **Actor**: an implementer (human or agent) driving a lane work package through
  `move-task --to for_review`, and the operator reading the tool's output.
- **Trigger**: the work package's deliverables include a brand-new directory, so
  the lane's `git status` reports it as one collapsed entry.
- **Desired outcome**: the auto-commit lands exactly the intended files, says so,
  and never names a cause it has not established.
- **Rule/invariant**: a commit request must name exact file paths; a directory
  pathspec is refused before anything is written, and any post-landing report
  must state whether the commit landed.
- **Boundaries**: the public `spec-kitty safe-commit` CLI keeps its own expansion;
  the non-owned lane's ownership policy is out of scope (C-003).

**Assumptions (from the operator brief, no interview needed)**: the defect is the
one in issue #6750; recovery of an implementer's finished deliverables must keep
working, so the collector expands rather than refuses; a WP that legitimately
produces a new directory is normal, not an error.

## Context

`move-task --to for_review` auto-commits the lane's finished deliverables through
`safe_commit` (the `_mt_commit_lane_deliverables` collector,
`cli/commands/agent/tasks_move_task.py`). The collector reads `git status` with
`untracked=None`, so a brand-new directory arrives as **one collapsed entry**
(`?? .zig-cache/`). `_lane_deliverable_paths` forwards that directory path
unexpanded, `preflight_commit` passes it through, and `git add`/`git commit
--only` expand it: the children land. Only afterwards does
`_assert_committed_paths_requested` compare the committed **file** set against the
literal **directory** request, find a superset, and raise
`SafeCommitUnrequestedPaths`, whose message states as fact that "a pre-commit hook
staged them". The collector then catches it and prints "could not auto-commit",
so a commit that landed is reported as an untouched failed attempt.

Observed in a real Zig lane: a commit carrying 13 generated `.zig-cache/**` paths
landed, followed by the false hook attribution, with the hook directory verified
empty.

`_assert_committed_paths_requested`'s own docstring asserts the invariant that
"every caller already expands directories to files before `safe_commit`". The
public `safe-commit` CLI honours it (it expands at the CLI layer, #2739 B11); the
lane collector does not, and nothing enforces it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A new directory of deliverables commits cleanly (Priority: P1)

An implementer creates a new directory of files (a new module, a fixture tree) and
runs `move-task --to for_review` with auto-commit. The tool commits exactly those
files, reports that it committed them, and says nothing about a hook.

**Why this priority**: this is the reported defect: the everyday "I added a new
directory" case produces a misleading diagnostic after a partial-looking commit.

**Independent Test**: drive the real collector against a git fixture whose only
untracked content is a directory, with an empty hooks directory; assert HEAD moved
once, the commit carries exactly the children, the tree is clean, and no
hook-attribution text is printed.

**Acceptance Scenarios**:

1. **Given** a lane worktree with an untracked directory `.zig-cache/` holding two
   files and an empty `core.hooksPath`, **when** the lane collector auto-commits,
   **then** HEAD advances once, the commit carries exactly both children, the
   working tree is clean, and the collector reports the commit (no hook claim).
2. **Given** the same fixture with one unrelated tracked file modified in the
   worktree, **when** the collector auto-commits, **then** that unrelated
   modification is not in the commit and stays in the working tree.

### User Story 2 - A directory argument is refused before anything is written (Priority: P1)

A caller hands `safe_commit` a directory path anyway (a new caller, or a future
regression). The call fails **before** HEAD or the index move, and the error says
what is wrong: `safe_commit` commits exact file paths, expand the directory first.

**Why this priority**: without a seam-level invariant the same misattribution
returns with the next caller; the fix must be structural, not one caller's patch.

**Independent Test**: call `safe_commit` with a directory in `paths` on a fixture;
assert the typed refusal, an unchanged HEAD, an unchanged `git status`, and no
hook wording in the message.

**Acceptance Scenarios**:

1. **Given** an untracked directory, **when** `safe_commit` is called with that
   directory as a requested path, **then** it raises the files-only refusal before
   any mutation, HEAD is unchanged and the index carries nothing new.
2. **Given** any committed set, **when** the request is exact file paths, **then**
   the refusal never fires.

### User Story 3 - A genuine hook sweep is still caught and correctly blamed (Priority: P2)

An operator's pre-commit hook runs `git add -u` and sweeps an unrelated modified
tracked file into the commit. The post-landing check must still catch that, name
the swept path, and say the commit landed.

**Why this priority**: the existing safety net must not be weakened to make the
false positive go away — the negative control proves both halves.

**Independent Test**: fixture with a real `pre-commit` hook that stages an
unrelated tracked edit; assert `SafeCommitUnrequestedPaths` fires naming only that
path, and that the collector's message says the commit landed.

**Acceptance Scenarios**:

1. **Given** a hook that sweeps a modified tracked file, **when** the collector
   auto-commits explicit files, **then** the unrequested-path warning fires,
   naming the swept path only, and reports the landed SHA.

### Edge Cases

- An untracked directory that becomes empty (or holds only ignored files) between
  the status read and the commit: the commit must not be attempted as a directory;
  if nothing is left to stage the existing `SafeCommitStagedTreeUnchanged` "no
  change" path applies.
- A symlinked directory: it is a single `120000` entry, never expanded (the public
  CLI's existing rule); it must not be mistaken for a directory to refuse.
- A tracked file whose path is also a directory name prefix: only a path that
  *is* a directory on disk is refused.
- A rename where one side is a deleted directory member: expansion yields the
  member paths, both sides preserved as today.
- Windows/POSIX separators: the refusal and the expansion both report
  repository-relative POSIX paths, as the existing comparison does (#2836).
- Generated artifacts outside the WP's `owned_files` that are merely unignored
  (the Zig `.zig-cache/` case): still committed by the non-owned collector. See
  C-003 — changing that is a policy decision, not part of this fix.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Collector expands collapsed directories | As a lane implementer, I want the auto-commit to request exactly the files git would stage so that a new directory of deliverables commits without a false hook warning. | High | Open | [build] | no — the red test asserts the children are in the commit *and* no hook text is printed; a no-op collector prints the hook warning today. |
| FR-002 | `safe_commit` refuses directory pathspecs pre-mutation | As an operator, I want a directory argument refused before HEAD or the index move so that no partial commit lands and no post-hoc attribution has to explain one. | High | Open | [build] | no — HEAD-moving is observed on the same fixture today. |
| FR-003 | Genuine hook sweeps still caught | As an operator, I want a hook-swept path still reported, naming only the genuinely extra paths, so that fixing the false positive does not disable the guard. | High | Open | [ratchet] | no — paired positive control on a real `pre-commit` hook. |
| FR-004 | Collector reports a landed commit truthfully | As a lane implementer, I want the collector to say the commit landed (with its SHA) when a recovery-class failure follows it, so that I never re-do work that is already committed. | High | Open | [build] | no — today's message for the same exception is "could not auto-commit". |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|--------|--------|
| NFR-001 | No extra git round trip on the healthy path | A clean lane auto-commit issues the same number of git invocations as before this change (one status probe plus the existing stage/commit/verify sequence). The refusal starts from a filesystem stat; it consults the index with one `git ls-files --stage` only after that stat finds a directory, to tell a submodule gitlink (a legitimate single-entry target) from a directory to expand, so the healthy path adds no git call. Verified by counting `git` invocations in the regression test. | Performance | Medium | Open |
| NFR-002 | Pre-mutation refusal is total | On a directory-argument refusal, zero index entries and zero refs are written: `git rev-parse HEAD` and `git status --porcelain` are byte-identical before and after. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|--------|--------|
| C-001 | Public CLI expansion unchanged | `spec-kitty safe-commit`'s own directory expansion (#2739 B11) keeps its behaviour and its expansion report; this mission adds a seam backstop, it does not move the CLI's expansion. | Technical | High | Open |
| C-002 | Existing error contract preserved | `SafeCommitUnrequestedPaths` keeps its type, `SAFE_COMMIT_UNREQUESTED_PATHS` code and `SafeCommitRecoveryFailed` "landed, carrying `commit_sha`" contract, so every existing handler keeps working; the new refusal is a separate `SafeCommitError` subclass raised before mutation. | Technical | High | Open |
| C-003 | No ownership-policy change | Whether the non-owned lane collector should refuse files outside the WP's `owned_files` (rather than sweep unignored generated artifacts) is a policy question for a maintainer; this mission records the finding and defers the change. | Business | Medium | Open |

### Key Entities

- **Lane deliverable set**: the absolute file paths the collector asks `safe_commit` to commit; must be exact files, never a directory pathspec.
- **Collapsed status entry**: one `?? dir/` record from `git status` when untracked files are not expanded; the value this mission stops carrying into a commit request.
- **Post-landing extra-path verdict**: the comparison of the committed file set against the requested file set; must only ever fire for paths the operation genuinely did not request.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A lane auto-commit whose only new content is a new directory produces exactly one commit carrying exactly that directory's files, leaves the working tree clean, and says nothing about a hook; the pre-fix code fails this on the message text and on the reported outcome. — [build] · no-op passable: no
- **SC-002**: When a commit hook stages an unrelated tracked file, the operator is told the commit landed (with its SHA) and exactly which swept path was added, never the requested ones; reverting either half of the fix (the expansion, the truthful reporting) turns a distinct assertion red. — [ratchet] · no-op passable: no
- **SC-003**: A commit request that names a directory is refused with a files-only message and zero repository mutations — HEAD, refs and index are byte-identical before and after. — [build] · no-op passable: no
