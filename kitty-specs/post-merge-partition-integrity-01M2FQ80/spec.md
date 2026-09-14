# Mission Specification: Post-merge partition integrity (#3942 + #4090)

**Mission Branch**: `issue-3942-merge-surface-authority`
**Created**: 2026-09-14
**Status**: Draft
**Input**: Remediate #3942 + #4090 (folding #4091) as ONE mission on the shared post-merge partition surface, kept as two distinct-but-not-sealed WP tracks. Operator rationale: the two defects share the surface/materialization effect, so co-locating them improves discovery of shared root causes and overlapping surfaces. Pre-spec 3-lens adversarial squad verified liveness red-first on HEAD `ecbf036328` (== `upstream/main`).

## Intent Summary (confirmed)

- **Primary actor**: a contributor/agent completing a mission — running `spec-kitty merge` and then post-merge lifecycle commands (`retrospect create`, `doctor mission-state`).
- **Trigger**: a mission merge (squash strategy) folding a lane/mission branch into the target.
- **Desired outcome**: (A) the merge never silently replaces target-newer `kitty-specs/` planning content with an older lane copy; (B) after a merge, every reader of mission state agrees on the same work-package lane states.
- **Invariant**: there is a single, honest post-merge authority for each partition artifact — merge writes must not lose newer target content without surfacing it, and post-merge reads must resolve to one canonical surface (or an explicitly-reconciled one).
- **Canonical terms**: *partition* (PRIMARY vs COORD), *surface* (the resolved status/planning home), *lane consolidation* (`spec-kitty merge` squash), *driver-covered artifact* (a `kitty-specs/` file with a custom merge driver) — all per the Terminology Canon footgun (`primary`/`merge` overloaded).

## Shared framing (both tracks)

The two tracks are facets of one question: **"After a merge, what content is authoritative for each partition artifact, and on which surface is it read?"** Track A is the **write** half (which bytes win when a merge reconciles divergent `kitty-specs/` files); Track B is the **read** half (which surface a post-merge reader trusts for WP lane state). The mission explicitly produces a cross-track root-cause synthesis (FR-009) rather than treating the tracks as hermetic.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Squash merge preserves target-newer planning content (Track A, #3942) (Priority: P1)

When a mission is squash-merged, a `kitty-specs/` planning file (e.g. `spec.md`, `plan.md`, `tasks/WP*.md`) that was edited more recently on the target must not be silently overwritten by an older copy carried on the lane/mission branch.

**Why this priority**: P1, catfooding-verified data loss. The squad drove the real squash path (`lanes/merge.py::integrate_mission_into_target(SQUASH)` → `git merge --squash -X theirs`) and observed `spec.md` and `tasks/WP01.md` target-newer content clobbered by older lane copies. Silent loss of reviewed planning content.

**Independent Test**: Construct a base `kitty-specs/` planning file, make a newer edit on the target and a conflicting older edit on the mission branch, run the squash consolidation, and assert the target-newer content survives OR the divergence is surfaced (not silently lost).

**Acceptance Scenarios**:

1. **Given** a `kitty-specs/<m>/plan.md` where target (main) has content newer than the mission branch's conflicting copy, **When** the mission is squash-merged, **Then** the target-newer content is retained (or the operation halts/reports the divergence) — never silently replaced by the older lane copy.
2. **Given** a driver-covered artifact (`meta.json`, `acceptance-matrix.json`, `issue-matrix.json`), **When** the same merge runs, **Then** the existing #2709/#2804 reconciliation behavior is preserved unchanged (no regression).
3. **Given** only a one-sided edit (target changed, mission branch did not), **When** the merge runs, **Then** the target edit is kept (git's normal behavior — the fix must not alter this).

---

### User Story 2 - Post-merge readers agree on work-package state (Track B, #4090) (Priority: P1)

After a mission is merged, `retrospect create` and `doctor mission-state` must resolve the same work-package lane states for the same mission — a merged/accepted mission must be retrospect-eligible.

**Why this priority**: P1, blocks the retrospective lifecycle terminus. The squad confirmed retrospect and doctor now share `resolve_status_surface`, but the primary-wins guard for a surviving diverged coord husk gates on `meta["merged_at"]`, whose production writer was deleted in #2258 and never re-added — so the guard is dormant and the divergence resurfaces.

**Independent Test**: Reproduce a merged mission whose coord surface is stale relative to primary; assert `retrospect create` and `doctor mission-state` report identical WP lane states (and that retrospect does not falsely raise `MISSION_NOT_COMPLETED`).

**Acceptance Scenarios**:

1. **Given** a merged mission where the primary partition records all WPs terminal but a diverged coord husk still records them non-terminal, **When** `retrospect create` runs, **Then** it resolves the primary (authoritative post-merge) state and proceeds — it does not raise `MISSION_NOT_COMPLETED`.
2. **Given** the same mission, **When** `doctor mission-state` runs, **Then** it reports the same terminal WP states as retrospect.
3. **Given** a merge of a completed mission, **When** the merge finishes, **Then** the post-merge authority marker the primary-wins guard depends on is actually written (no reader gating on an unwritten marker).

---

### User Story 3 - Event-stream counts are consistent post-merge (Track B, folds #4091) (Priority: P2)

After a merge unions two event streams, `status.json` `event_count` must not undercount `status.events.jsonl` (the SNAPSHOT_DRIFT the #4090 fix praises must be actually eliminated for the merged mission).

**Why this priority**: P2, same "merge unions two event streams and they disagree" root as Story 2's propagation side; folding #4091 here lets one fix (or one reconciliation) close both.

**Independent Test**: After a merge that unions event logs, assert the reduced snapshot's `event_count` equals the actual line count of the unioned `status.events.jsonl`.

**Acceptance Scenarios**:

1. **Given** a merge that unions two `status.events.jsonl` streams, **When** the post-merge snapshot is materialized, **Then** `event_count` equals the number of events in the unioned log.

---

### User Story 4 - Cross-track root-cause synthesis (Priority: P2)

The mission delivers an explicit written analysis of the shared post-merge-partition authority root cause, mapping Track A's write authority and Track B's read authority onto one model of "authoritative content per artifact per surface," and stating whether a single unifying seam exists or the two are genuinely disjoint.

**Why this priority**: P2, this is the operator's stated reason for keeping the two issues in one mission. It converts co-location into concrete cross-track value.

**Independent Test**: A reviewer can read the synthesis and confirm it cites both seams, states the shared/disjoint verdict with evidence, and records any overlap discovered (or its absence) for the epic owners (#2907, #2160).

**Acceptance Scenarios**:

1. **Given** both tracks implemented, **When** the synthesis is reviewed, **Then** it names the write seam (`lanes/merge.py` driver registry) and the read seam (`surface_resolver.py` + the `merged_at` marker) and gives a defended shared-vs-disjoint verdict.

### Edge Cases

- A `kitty-specs/` file added only on the mission branch (no target copy) — must still land (not treated as a clobber).
- A merge with `--keep-worktree`/`--keep-branch` retention — the coord husk deliberately survives; the post-merge read must still resolve to the authoritative surface.
- A mission merged on a `single_branch`/`LANES` topology (no coord partition) — readers must trivially agree (no regression).
- `merged_at` present in legacy fixtures but absent in real merges — the fix must not depend on test-only data.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Preserve target-newer planning files on squash | As a contributor, I want squash merges to keep target-newer `kitty-specs/` planning content so that reviewed edits are not silently lost. | High | Open |
| FR-002 | Surface (not silently drop) planning-file divergence | As a contributor, I want any lane-vs-target divergence on a `kitty-specs/` planning file reported so that I can see when a merge would overwrite content. | High | Open |
| FR-003 | Preserve existing driver-covered reconciliation | As a maintainer, I want the #2709/#2804 driver/gate-artifact behavior unchanged so that the fix adds no regression. | High | Open |
| FR-004 | Retrospect resolves post-merge-authoritative state | As an agent, I want `retrospect create` to read the authoritative post-merge surface so that a merged mission is retrospect-eligible. | High | Open |
| FR-005 | Retrospect and doctor agree | As a contributor, I want `retrospect create` and `doctor mission-state` to report identical WP lane states for a merged mission. | High | Open |
| FR-006 | Post-merge authority marker is written | As a maintainer, I want the merge to write the marker the primary-wins guard depends on (or the guard to not depend on an unwritten marker) so that the guard is not dormant. | High | Open |
| FR-007 | Event-count consistency post-merge (#4091) | As a contributor, I want `status.json` `event_count` to match the unioned `status.events.jsonl` after a merge. | Medium | Open |
| FR-008 | Regression guards for both tracks | As a maintainer, I want red-first tests that fail on today's HEAD and pass after the fix, guarding both the write-clobber and the read-divergence classes. | High | Open |
| FR-009 | Cross-track root-cause synthesis | As the operator, I want a written shared-root-cause analysis mapping the write and read authorities onto one post-merge-partition model. | Medium | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No merge-time silent data loss | Zero silent overwrites of target-newer `kitty-specs/` content on squash; every overwrite avoided or reported (0 silent-loss cases in the guard suite). | Reliability | High | Open |
| NFR-002 | Reader agreement is deterministic | For a given merged mission state, `retrospect create` and `doctor mission-state` agree on 100% of WP lane states across repeated runs. | Reliability | High | Open |
| NFR-003 | Complexity ceiling | Any function touched stays at cyclomatic complexity ≤15 (ruff C901 / Sonar S3776), extracting tested helpers as needed. | Maintainability | Medium | Open |
| NFR-004 | Targeted test cost | New/changed tests run in the targeted blast radius without invoking the full suite. | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Single canonical authority | Extend the existing merge-driver registry and `surface_resolver` authorities; do not introduce a second competing authority (charter single-canonical-authority principle). | Technical | High | Open |
| C-002 | Name overloaded senses | All spec/plan/code prose must name the `primary`/`merge`/`routing` sense used (Terminology Canon footgun). | Technical | High | Open |
| C-003 | No coord dogfooding | The mission itself is minted `single_branch` (Track B is a coord-topology bug; a coord mission would dogfood the defect). | Technical | High | Open |
| C-004 | ATDD red-first | Each track's first WP must reproduce its defect in-repo on HEAD before any fix is built (tracker is systematically stale — verify, never assume). | Technical | High | Open |

### Key Entities

- **Partition artifact**: a `kitty-specs/` file (planning doc, `meta.json`, gate matrix, event log) that a merge must reconcile and a reader must resolve.
- **Merge driver registry** (`_MERGE_DRIVERS`, `lanes/merge.py`): the allowlist of artifact classes reconciled during squash; the write authority.
- **Status surface** (`coordination/surface_resolver.py::resolve_status_surface`): the resolved read home (coord vs primary) for mission state; the read authority.
- **`merged_at` marker** (`meta.json`): the post-merge signal the primary-wins guard depends on — currently unwritten.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The Track A red-first test (target-newer `plan.md`/`WP*.md` clobber via real squash) is RED on HEAD `ecbf036328` and GREEN after the fix.
- **SC-002**: The Track B red-first test (merged mission with stale coord husk → retrospect vs doctor disagreement, driven through the real readers) is RED on HEAD and GREEN after the fix.
- **SC-003**: `retrospect create` and `doctor mission-state` agree on 100% of WP lane states for the reproduced merged mission.
- **SC-004**: The #2709/#2804 and #3981 existing behaviors remain green (no regression in the driver/gate-artifact and implement-gate suites).
- **SC-005**: The cross-track synthesis (FR-009) is delivered and cites both seams with a defended shared-vs-disjoint verdict.
