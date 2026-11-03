# Mission Specification: Keep a coordination commit that lands before a first-run teardown

**Mission Branch**: `fix-6871-first-run-late-coord`
**Created**: 2026-11-02
**Status**: Draft
**Input**: Issue #6871 — `consolidate` (first run, not `--resume`): a coordination commit landing between the gate and teardown is still deleted silently.

## Problem

`spec-kit consolidate` ends with a teardown phase that deletes the Mission's coordination
branch (`kitty/mission-<slug>`). The `--resume` path protects a commit that landed on that
branch after the merge verified its landing: `_land_late_coordination_commits` projects the
window onto the target, commits it, and then **asserts** every coordination record the window
carried is byte-identical on the target before the branch is deleted (#5570, #6791, #6857).
The first-run path returns early (`if not run.is_resume: return`), so a coordination commit
that lands *after* the merge captured `coord_tip_after_projection` — its own last write to the
coordination ref — is destroyed with the branch, at exit 0, with no projection and no assertion.

The window is real in operator terms: a late `agent issue-verdict` write, a concurrent
status emit, or the operator following a refusal's own instruction to "commit it on the
coordination branch" all land inside it. Losing the commit means the Mission record never
reflects the work that shipped, and the operator has to hand-assemble the landing.

## Goal

A first run gets the same protection the `--resume` path already has, without weakening it:

- a late coordination commit that **can** be landed is landed on the target and then proven
  landed (the project's own post-projection assertion) before the branch is deleted;
- a late coordination commit that **cannot** be landed refuses loudly — non-zero exit, the
  coordination branch, its worktree and the Mission's coordination marker all kept — and the
  refusal names the recovery, which is `spec-kitty consolidate --resume`;
- a clean first run projects nothing and behaves exactly as it does today (no new commit, no
  new failure);
- the `--resume` window (`pre_mutation_coord_sha..branch`) and its #6857 assertion are
  unchanged.

## Scope decisions

### The first-run window starts at the run's own last verified coordination write

The resume window starts at the persisted pre-mutation snapshot, because a resume has no
in-memory record of what the merge verified. A first run does: `coord_tip_after_projection`
is captured at the end of the bookkeeping phase, after every merge-owned coordination write
(`phase_bookkeeping._phase_record_done_and_project`). Everything at or before that tip was
already projected onto the target by the merge itself; anything after it is late. Anchoring
the first-run window there makes a clean run a provable no-op instead of re-walking the whole
merge (which would re-project stale primary artifacts and manufacture refusals).

### The approved tip moves only when the landing is proven

After the projection and the assertion both succeed, the run records the projected tip as the
tip teardown approved (`coord_tip_after_projection`), so the existing projection teardown gate
and the compare-and-swap branch delete anchor on the tip whose content is proven landed. A
commit landing after that still moves the ref and still refuses. Nothing is approved merely
because it was read.

### A run with no recorded anchor keeps today's behaviour

If a first run has neither `coord_tip_after_projection` nor a coordination checkpoint, there is
no proof of what the tip held when the merge verified it, so there is no window to build and
nothing to compare against. That case is not the one this Mission fixes (it is a Mission whose
coordination placement does not resolve); it keeps its current behaviour and is recorded as a
residual in the PR's `## Deferred`, not silently "fixed" by an unprovable refusal.

## User Scenarios & Testing

### User Story 1 - A late coordination record survives a first-run teardown (Priority: P1)

An operator (or a concurrent step) commits a verdict record on the coordination branch after
the merge captured the tip it verified, and then teardown runs. The record must be on the
target ref afterwards, and the branch must be deleted only once it is proven there.

**Why this priority**: this is the silent data loss the issue reports, and the only outcome
that leaves the Mission record truthful without a human hand-assembling the landing.

**Independent Test**: build the coord-run fixture the teardown gate tests use, land one
coordination commit after `coord_tip_after_projection`, run the teardown phase, and assert the
record's bytes are at the target ref and the branch is gone.

**Acceptance Scenarios**:

1. **Given** a first run whose coordination tip moved after `coord_tip_after_projection`,
   **When** teardown runs, **Then** the late record is committed on the target and the branch
   is deleted and flattened.
2. **Given** the same run, **When** teardown runs, **Then** exactly one late-projection commit
   is made on the target (never one per record, never one on a clean run).
3. **Given** a clean first run (tip unmoved), **When** teardown runs, **Then** no projection
   commit is made and the branch is deleted and flattened as today.

### User Story 2 - A late record that cannot be landed refuses loudly (Priority: P1)

Some late commits cannot be expressed by a projection: a deletion of a record the target still
holds, or a coordination copy that would overturn a judgement the target already established.
Those must refuse before the branch is deleted.

**Why this priority**: silence is the defect. A refusal that keeps the triple and names the
recovery is a correct outcome; a deletion is not.

**Independent Test**: land a late commit that deletes a coordination record the target holds,
run the teardown phase, and assert the typed refusal, the surviving branch/worktree/marker and
the `--resume` recovery in the message.

**Acceptance Scenarios**:

1. **Given** a late commit that deletes a record the target holds, **When** teardown runs,
   **Then** it raises the coordination-teardown refusal (non-zero exit), the coordination
   branch still exists, and the Mission marker is intact.
2. **Given** the same run, **When** the refusal text is read, **Then** it names the
   coordination branch, the target, and `spec-kitty consolidate --resume` as the recovery.

### User Story 3 - The `--resume` guarantee is not traded away (Priority: P2)

The resume path's window and post-projection assertion are the fix #6857 shipped; the first-run
fix must not narrow them.

**Independent Test**: the existing `--resume` late-teardown suite (projection of a verdict
committed after a teardown refusal, the evidence-preserving matrix refusal, the unbuildable
window refusal) passes unchanged.

**Acceptance Scenarios**:

1. **Given** the resume suite, **When** it runs, **Then** every case passes with no test edited
   to accommodate the first-run change.

## Functional Requirements

- **FR-001**: On a first run (`is_resume` False) whose coordination tip is ahead of
  `coord_tip_after_projection`, teardown projects the window onto the target through the same
  seams the resume path uses (`_project_status_bookkeeping_to_target`,
  `_post_checkpoint_mission_paths`, `project_late_gate_matrix_commits`) and commits it as one
  bookkeeping commit.
- **FR-002**: After that projection the first run runs `assert_late_window_landed` over the
  same window, so a record the projection could not carry refuses instead of being deleted.
- **FR-003**: The first run's window base is `coord_tip_after_projection`; the resume path keeps
  `state.pre_mutation_coord_sha`. Neither path falls back to the other's base.
- **FR-004**: A first run whose coordination tip equals `coord_tip_after_projection` makes no
  commit and no console claim; teardown proceeds exactly as today.
- **FR-005**: A first run with no `coord_tip_after_projection` and no coordination checkpoint
  builds no window (behaviour unchanged; documented as a residual).
- **FR-006**: Every first-run late-window refusal keeps the coordination branch, its worktree
  and the Mission's coordination marker, and names `spec-kitty consolidate --resume`.
- **FR-007**: A refusal that already names its own remedy (deletion-cannot-be-expressed,
  evidence-would-be-lost, unreadable gate document) keeps that remedy: the first-run path reuses
  `_late_projection_refusal` / `_late_projection_remedy`, so no two refusal kinds share a remedy.
- **FR-008**: The projection teardown gate and the compare-and-swap branch delete still anchor
  on a recorded tip; the first-run projection updates that anchor only to a tip whose content the
  assertion proved landed, and only while the ref is still at that tip.
- **FR-009**: No new CLI flag, no new configuration key, no change to the exit-code contract
  (`CoordinationTeardownError` = non-zero, `COORD_LATE_PROJECTION_REFUSED` code unchanged).

## Key Entities

- **coord_tip_after_projection** — the coordination tip the merge verified, captured at the end
  of the bookkeeping phase; the gate's compare-and-swap anchor and, now, the first-run window
  base.
- **late window** — `base..coordination tip`; the records changed in it that must be proven
  landed before deletion.
- **coordination triple** — coordination branch, worktree and Mission marker; kept or torn down
  together (INV-2).

## Non-Goals

- Changing the approval/evidence axis (`wp_evidence`): the single-agent `REVIEW_NOT_INDEPENDENT`
  / `IMPLEMENTATION_MISSING` shape from #7082's reproduction is a governance decision (may one
  actor review the work it implemented?) and its refusals already name their recoveries. It is
  reported, not changed, here.
- Making a no-anchor first run refuse: unprovable, and it would strand Missions whose
  coordination placement does not resolve.
- Any change to `--abort`, rollback, or the retention/`--keep-branch` flags.

## Success Criteria

- The red test written first (a late commit on a first-run teardown) fails before the change and
  passes after it.
- The existing late-teardown, projection-teardown and teardown-refusal suites pass without
  edits that weaken them.
- A real `consolidate` on the coordination fixture still lands and tears down at exit 0 with no
  extra commit.
