# Mission Specification: coord-topology `accept` commits its own coordination-worktree residual

**Mission Branch**: `issue-7091-accept-coord-residual-artifact-commit`
**Created**: 2026-11-03
**Status**: Draft
**Input**: GitHub issue #7091 — "accept: coord-topology residual artifact commit refuses because it stages the coord worktree's mission-events.jsonl from the primary checkout".

Guidance recorded from the operator brief (batch 9, machinery-first): small, tightly
scoped fix; red-first through the pre-existing entry point; do not weaken or skip any
gate; no change to readiness judgement; changelog as a per-PR fragment; the operator
merges, never this agent.

## Problem

`spec-kitty accept --mission <handle>` for a coordination-topology mission reaches
readiness `ready`, records the acceptance metadata, commits the coordination-owned
derived artifacts to the coordination branch — and then fails its own residual artifact
commit and exits 1. The failure is bookkeeping plumbing, not a mission blocker:

```
✗ primary (<target-branch>): refused — .worktrees/<handle>-coord/kitty-specs/<handle>/mission-events.jsonl: error;
primary (<target-branch>): safe_commit: refusing to stage path under .worktrees/: ...
```

The defect is a classification gap in the residual path, not in readiness:

1. `accept`'s residual scan unions two legs — tracked-modified files in the PRIMARY
   checkout, and tracked-modified files in the mission's coordination worktree
   (`accept.py::_primary_dirty_paths` / `_coord_dirty_paths`), and hands BOTH as one
   absolute-path batch to `commit_for_mission`.
2. `commit_for_mission` groups the batch by PARTITION using the single file→kind
   classification authority (`is_coord_residue_churn` over
   `mission_runtime.kind_for_mission_file`).
3. `mission-events.jsonl` — the mission's append-only event log, which `spec-kitty next`
   writes through the COORD-routed `STATUS_STATE` write seam
   (`runtime/next/next_invocation_lifecycle.py::emit_mission_next_invoked`) — has no
   entry in `_MISSION_FILE_KIND_BY_BASENAME`. The classifier therefore returns `None`,
   `None` is never coordination residue, and the router routes the file to the PRIMARY
   partition.
4. The PRIMARY leg then hands `safe_commit` an absolute path that physically lives under
   `.worktrees/`. `safe_commit` correctly refuses that (`#2155` / `#3784`: no
   `.worktrees/`-nested path may enter a primary-root commit bundle), so
   `_run_residual_acceptance_commit` raises `ResidualCommitError` and the command exits 1.

Reproduced on current `main` in a real coordination-topology fixture (canonical
`CoordinationWorkspace` worktree, full ULID / `mid8` / `<slug>-<mid8>` layout, target
branch `feat/<handle>`): dirtying only `kitty-specs/<handle>/mission-events.jsonl` inside
the coordination worktree reproduces the issued error string verbatim; the coordination
matrix commits and the primary surface refuses. This is the same failure #7035's accept
reported.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A ready coord-topology mission can record its own acceptance (Priority: P1)

An agent or operator accepts a coordination-topology mission whose readiness checks pass.
Accept's residual tidy-up commits every coordination-owned artifact it can own, treats the
non-artifact mission event log as already handled (it is keep-local, #5669), reports that
the log was left where it lives, returns 0, and prints the consolidate instructions that
follow a successful accept.

**Why this priority**: this is the issue's whole impact. Missions that are genuinely
ready report as failed accepts, so the close-out sequence cannot continue without a human
reading the tool output to learn that readiness actually passed.

**Independent Test**: build a real coordination-topology mission, dirty
`mission-events.jsonl` in the coordination worktree only, call
`accept.py::_run_residual_acceptance_commit` (the pre-existing residual entry point):
before the change it raises `ResidualCommitError`; after it returns a result with no
refused/error surface, the coordination-owned matrix dirty in the same run still commits
on the coordination branch, the primary branch has no new commit, and the log is still
where it lives (uncommitted, by design).

**Acceptance Scenarios**:

1. **Given** a coordination-topology mission whose coordination worktree has a
   tracked-modified `mission-events.jsonl`, **When** accept's residual artifact commit
   runs, **Then** the log is excluded from the commit batch and the call returns without
   raising.
2. **Given** the same run, **When** the commit completes, **Then** the coordination-owned
   matrix is committed on the coordination branch, the primary branch gains no commit,
   and the log is still tracked-modified in the coordination worktree (it is not committed
   anywhere).
3. **Given** the same run, **When** the command finishes, **Then** the acceptance result
   carries a note naming the deferred path, and no residual-commit failure reaches
   `_raise_on_finalize_errors`, so the command's exit is 0 on the success path (the
   readiness/acceptance result is unchanged).

### User Story 2 - The keep-local ruling is respected, not reversed (Priority: P1)

A maintainer who recorded the #5669 ruling ("`mission-events.jsonl` is not a mission
artifact, and its churn must stay real dirt for the destructive gates") sees it untouched:
no kind is added for the log, the global churn owner's answer does not change, and the
scoped survivor lives in the residual committer, the same per-gate pattern #5669 used.

**Why this priority**: classifying the log would be the obvious shortcut, and it silently
exempts gate rows the ruling exists to protect (it fails the pinned C-002 guard). A fix
that reverses a recorded decision is not a fix.

**Independent Test**: `is_self_bookkeeping_churn` and `is_toolchain_generated_churn` still
answer `False` for `kitty-specs/<slug>/mission-events.jsonl`, the classifier still returns
`None`, and the accept survivor is derived from that same `None` verdict.

**Acceptance Scenarios**:

1. **Given** a mission-root `mission-events.jsonl`, **When** the classifier and the global
   churn owner are asked about it, **Then** the classifier returns `None` and both churn
   predicates return `False` (unchanged from `main`).
2. **Given** the accept survivor, **When** it decides what to defer, **Then** it consults
   `kind_for_mission_file` (not a filename literal) and defers exactly the paths whose
   verdict is `None`.

### User Story 3 - Nothing else moves (Priority: P2)

A maintainer landing this sees only the residual committer, its reporting note and the
tests: no gate changes, no change to what `accept` considers ready, no classifier or
partition change, no widening of the narrow status-state predicate, and no change to how a
flat or single-branch mission commits its own mission event log.

**Why this priority**: the issue is plumbing; a broad touch here risks the acceptance
semantics the fleet depends on.

**Independent Test**: the existing accept residual, acceptance-matrix partition and
artifact-partition mapping suites stay green unchanged, a flat-mission test proves a dirty
`mission-events.jsonl` still commits on the mission's own branch, and a narrowness test
proves a PRIMARY-classified artifact stranded in the coordination worktree is still
refused loudly.

**Acceptance Scenarios**:

1. **Given** a flattened (non-coordination) mission with a dirty
   `mission-events.jsonl`, **When** its residual commit runs, **Then** the file still
   commits on the current unprotected branch as it does today.
2. **Given** a `spec.md` stranded (tracked-modified) in a coordination worktree,
   **When** the residual commit runs, **Then** it still routes PRIMARY and `safe_commit`
   still refuses the `.worktrees/` path — the survivor is for non-artifacts only.
3. **Given** the narrow `is_status_state_path` predicate, **When** it is asked about
   `mission-events.jsonl`, **Then** the answer is unchanged (`False`): the status pair
   stays exactly `status.events.jsonl` / `status.json`.

## Edge Cases

- **The file is untracked in the coordination worktree.** Accept's residual scan
  deliberately excludes untracked (`??`) paths (`_dirty_paths_with_prefix`), on both
  legs; this change does not alter that. An untracked event log is not swept in.
- **A stale PRIMARY-checkout copy of `mission-events.jsonl` is dirty while the
  coordination copy is clean.** The classification fix makes the router report it as
  coordination residue and never land it on the target branch — the existing
  `COORD_RECORD_IN_ROOT_CHECKOUT` fate, matching how `status.events.jsonl` already
  behaves.
- **A coord-less (flat / single-branch) mission.** There is no coordination split, so
  the same kind resolves to the mission's own branch; nothing changes for those missions.
- **Another coord-owned mission-root file is still unclassified** (e.g. an
  agent-authored review report). Out of scope for this issue: it is not written by the
  coordination write seam, it is not what #7091 reports, and each such family needs its
  own partition decision. Recorded in `## Deferred` on the PR.
- **`mission-events.jsonl` is appended by `next` while a commit runs.** The residual
  commit is a single atomic stage-and-commit per surface, exactly as today; a later
  append is ordinary post-commit dirt for the next run, not a new failure mode.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Defer non-artifact coordination residuals | As an agent, I want accept's residual artifact commit to exclude a coordination-worktree path that classifies to no mission artifact kind, so that a ready mission records its own acceptance instead of exiting 1 over bookkeeping plumbing. | High | Open | [build] | no — the pre-fix run raises `ResidualCommitError` for exactly this path |
| FR-002 | Report the deferral | As an operator, I want the acceptance result to name every deferred path and why it is left uncommitted, so that a still-dirty coordination worktree is a documented outcome, never a silent drop. | High | Open | [build] | no — the paired control asserts an empty deferral adds no note |
| FR-003 | Keep classified dirt loud | As a maintainer, I want a PRIMARY-classified path stranded in the coordination worktree to keep routing PRIMARY and keep being refused by `safe_commit`, so that the survivor is not a blanket "ignore coordination-worktree dirt". | High | Open | [ratchet] | no — the narrowness fixture still sees the `.worktrees/` refusal |
| FR-004 | Keep the keep-local ruling intact | As a maintainer, I want `mission-events.jsonl` to stay unclassified and to keep answering `False` from `is_self_bookkeeping_churn` / `is_toolchain_generated_churn`, so that the #5669 C-002 boundary (its churn is real dirt for the destructive gates) is untouched. | High | Open | [ratchet] | no — the #5669 C-002 guard fails if the log is classified |
| FR-005 | Flat missions unchanged | As an operator of a flat mission, I want my mission event log still committed on my mission's own branch so that this coordination fix does not regress coord-less topologies. | Medium | Open | [ratchet] | no — the paired flat-fixture test commits the file on its own branch |
| FR-006 | Red-first regression proof | As a reviewer, I want a test that fails on `main` through `_run_residual_acceptance_commit` and passes after the change so that the defect is pinned at the seam that failed. | High | Open | [build] | no — the pre-fix run raises `ResidualCommitError` naming the `safe_commit` refusal |
| FR-007 | Survivor is classifier-derived | As a maintainer, I want the deferral decision derived from `kind_for_mission_file` (not a filename literal or caller-asserted partition) so that the one classification authority stays the only authority and the survivor retires itself if the log ever gains a kind. | Medium | Open | [ratchet] | no — a literal-keyed survivor would keep deferring a later-classified file |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Proportional cost | The survivor is a pure classifier pass over paths the residual commit already scanned; the reporting note adds one `git status` in the coordination worktree per `accept` run (a once-per-mission command) and no new import on a hot path. | Performance | Medium | Open |
| NFR-002 | Acceptance semantics untouched | Readiness, acceptance-matrix verdicts, acceptance-metadata recording and the protected-branch refusal policy behave byte-identically; only the residual commit's handling of this non-artifact path (and its reporting note) changes. | Reliability | High | Open |
| NFR-003 | Classified dirt stays loud | A coordination-worktree residual that classifies to a PRIMARY kind (real misplaced dirt) still refuses through the existing `safe_commit` `.worktrees/` guard, and a classified COORD kind still commits on the coordination branch — no silent drop, no silent retarget. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | One classification authority | The deferral verdict must come from `mission_runtime.kind_for_mission_file`; no accept-local filename literal, and no caller-asserted partition override in the commit router. | Technical | High | Open |
| C-002 | No gate weakening | No readiness check, residue gate, protected-branch guard, churn-owner predicate or `.worktrees/` staging refusal may be relaxed, skipped or bypassed to make accept pass. In particular the #5669 keep-local ruling (the log stays real dirt for the destructive gates) is preserved, not reversed. | Technical | High | Open |
| C-003 | Scope ceiling | Only `accept.py`'s residual committer and reporting note change, plus the tests that cover them and the mission's own planning artifacts; `safe_commit`, the commit router's grouping, the classifier, the partition sets and `accept`'s readiness pipeline are untouched. | Technical | High | Open |

### Key Entities

- **Mission event log** (`mission-events.jsonl`): the append-only per-mission event log
  `spec-kitty next` writes through the coordination-routed status seam; unclassified by
  ruling (#5669), keep-local, and real dirt for the destructive gates.
- **Deferred residual**: a coordination-worktree residual path whose classifier verdict is
  `None`; not a mission artifact, so accept neither commits it to a surface nor fails on
  it, and reports it.
- **Residual artifact commit**: accept's post-readiness tidy-up that commits leftover
  derived artifacts from both checkouts through one commit-router call.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The red-first regression test fails on `main` with the issued
  `safe_commit: refusing to stage path under .worktrees/` refusal and passes on the
  branch (1/1 flip). — [build] · no-op passable: no
- **SC-002**: After the fix, the same coordination-topology fixture commits the
  coordination-owned matrix, adds 0 commits to the primary branch, and leaves the
  deferred log in exactly 1 place (tracked-modified in the coordination worktree, not
  committed on either branch), with 1 acceptance note naming it. — [build] · no-op passable: no
- **SC-003**: `kind_for_mission_file(".../mission-events.jsonl")` still returns `None`, and
  `is_self_bookkeeping_churn` / `is_toolchain_generated_churn` still return `False` for it
  (the #5669 C-002 guard green, unchanged). — [ratchet] · no-op passable: no
- **SC-004**: The pre-existing accept residual, acceptance-matrix partition, artifact
  partition mapping, #5669 survivor and write-surface placement suites pass unchanged
  (0 new failures). — [ratchet] · no-op passable: no
