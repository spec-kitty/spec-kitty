# Data Model: Issue-Matrix Partition Read Integrity & Merge Verdict-Terminality

**Phase 1** — conceptual entities and invariants. No new persisted schema; existing artifacts and
git state are modelled to make the resolution/enforcement rules precise.

## Entities

### IssueMatrix

- **Represents**: the per-mission record of how each cited GitHub issue is discharged.
- **Fields**: `rows: map<issue_ref, IssueMatrixRow>`.
- **Persisted as**: `issue-matrix.json` (+ legacy `.md`) — classified `MissionArtifactKind.ISSUE_MATRIX`,
  a COORD-partition kind (`src/mission_runtime/artifacts.py`).
- **Owning partition**: COORD on coord/lanes-with-coord topologies; PRIMARY on branch-flat
  (single_branch/lanes) topologies.

### IssueMatrixRow

- **Fields**: `issue_ref` (e.g. `#1234`), `verdict: Verdict`, provenance (actor/wp/surface).
- **Verdict (enum)**: `unknown`, `in-mission`, `fixed`, `verified-already-fixed`,
  `deferred-with-followup`, `not-applicable`.
- **Terminality invariant**:
  - **Non-terminal**: `unknown`, `in-mission`.
  - **Terminal**: `fixed`, `verified-already-fixed`, `deferred-with-followup`, `not-applicable`.
  - A non-terminal verdict on a **gating** row MUST NOT survive to mission `done`/merge (FR-006).

### GatingIssueReference

- **Represents**: a bare `#NNNN` citation in the mission's spec/tasks that obliges a matrix row.
- **Discovery source**: the PRIMARY partition (spec/plan/tasks), on every topology (FR-003).
- **Non-gating** (no row required): context-only citations (`Follow-up:`, `see #`, `parent`, `epic`)
  and PR/commit references (`PR #NNNN`, `/pull/NNNN`).

### Partition

- **Values**: `PRIMARY` (stable planning surface: spec/plan/tasks + reference discovery),
  `COORD` (lifecycle surface: status/notes/trace/issue-matrix + authored verdicts).
- **Rule**: reference discovery always reads PRIMARY; matrix verdicts read the matrix's owning
  partition (COORD on coord topology).

### LifecyclePhase (the surface-selection authority)

The read surface is chosen by `resolve_lifecycle_phase` — the SAME authority the write path uses — so
read and write can never diverge. It is driven by durable git signals, NOT by coord-worktree
materialization:

```
                 baseline_merge_commit present?
                        │
             ┌──────────┴───────────┐
            no                      yes
             │                       │
      PRE_CONSOLIDATION   Target Ref (meta.target_branch) exists?
      (coord topology →         │
       read coord branch   ┌────┴─────┐
       ref)               yes         no
                           │           │
                     CONSOLIDATED   completion evidence (mission_number OR all WPs done)?
                     (coord →         │
                      read coord   ┌──┴───┐
                      branch ref)  yes    no
                      #5171 case    │      │
                              PUBLISHED  PRE_CONSOLIDATION
                              (E2 → read
                               consolidated
                               PRIMARY ref)
```

- **#5171 is the CONSOLIDATED case**: coord branch retained, Target Ref (planning branch) still
  present ⇒ verdict written to (and read from) the coordination branch ref.
- **Caveat**: `meta.target_branch` is the planning branch (distinct from `meta.coordination_branch`);
  for a mission targeting a durable trunk (`main`) it is never deleted ⇒ phase stays CONSOLIDATED ⇒
  post-merge verdicts always route to the coordination branch. PUBLISHED/E2 only engages for missions
  whose Target Ref is a deletable per-mission branch.

### Read source resolution & fail-closed

Given the phase, the consumer reads the artifact **content** from the resolved ref (`git show
<ref>:<path>`; existence via `git rev-parse --verify` / `coord_branch_has_committed_artifact`):

- **PUBLISHED** ⇒ consolidated PRIMARY ref (`_resolve_consolidated_e2_target`).
- **CONSOLIDATED / PRE_CONSOLIDATION** (coord topology) ⇒ coordination branch ref.
- **Materialized worktree present** ⇒ the on-disk directory (unchanged fast path).
- **Fail-closed (NFR-002)**: resolved ref absent (deleted), content probe error, or empty authored set
  while gating references exist ⇒ REFUSE — never fall back to PRIMARY residue, never a vacuous PASS.

### ResolvedSurface (existing)

- Returned by `resolve_artifact_surface` — `(path, surface_kind)` where `surface_kind ∈ {PRIMARY,
  COORD}`. The new branch-ref read authority extends resolution to yield COORD *content* when the
  surface is `UNMATERIALIZED_RETAINED` rather than degrading to PRIMARY.

## Consumers (and required behavior)

| Consumer | Reference discovery | Matrix/verdict read | Enforcement |
|----------|--------------------|--------------------|-------------|
| `status/doctor.py::check_issue_matrix` (reference) | PRIMARY | COORD (`coord_read_dir_for`) | reports |
| mission-review Gate 4 (FR-001/002) | PRIMARY | COORD + branch-ref (FR-005) | PASS/FAIL |
| merge completeness gate (FR-003/004) | PRIMARY (via seam) | COORD + branch-ref (FR-005) | gate |
| merge terminal-verdict (FR-006) | — | COORD + branch-ref | block/warn |
| move-task blocker (reference) | — | COORD (already correct) | block on `done` |

## Validation rules

- A gating reference with no row ⇒ gate FAIL (never "nothing to enforce").
- A gating row with a non-terminal verdict at `done`/merge ⇒ block-mode refusal / warn-mode listing.
- Reads on branch-flat topologies resolve to PRIMARY and are byte-for-byte unchanged.
