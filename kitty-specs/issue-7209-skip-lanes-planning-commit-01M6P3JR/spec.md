# Mission Specification: `consolidate --skip-lanes` records an evidence window it can judge

**Mission Branch**: `issue-7209-skip-lanes-planning-commit`
**Created**: 2026-11-05
**Status**: Draft
**Input**: Issue #7209 — `consolidate --skip-lanes always refuses EVIDENCE_WINDOW_UNCOMPUTABLE: its synthesized lanes manifest records no planning commit`

## Problem

`spec-kitty consolidate --skip-lanes` exists to complete a direct-on-target Mission — one
whose work packages were committed straight onto the target branch, with no lane branch and
no `lanes.json` (the sanctioned #2745 fallback). The evidence axis added by #6715 asks every
approved work package for the change it made inside `planning_commit_sha..<tip>`. The
`--skip-lanes` path synthesizes its own `LanesManifest` (`entry_preflight._synthesize_no_lane_manifest`)
and leaves `planning_commit_sha` unset, because no `lanes.json` exists to record one. The
window is therefore uncomputable for every work package, so the run refuses
`EVIDENCE_WINDOW_UNCOMPUTABLE` on every mission this flag exists to serve. No attestation
lifts that code, and the refusal's recovery advice (`spec-kitty agent mission finalize-tasks`)
addresses a `lanes.json` the mission by definition does not have.

This is a product gap, not a stale fixture: the three red nodes in
`tests/specify_cli/cli/commands/test_issue_2745_merge_skip_lanes.py` are kept red by the
#7175 fixture re-seed (PR #7221) precisely because the fix belongs here.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A direct-on-target Mission completes with `--skip-lanes` (Priority: P1)

An operator who implemented a Mission's work packages directly on the target branch runs
`spec-kitty consolidate --skip-lanes`. The consolidated evidence axis now has a real window
to judge — everything the target branch gained since this Mission's planning artifacts
appeared — so a work package whose change touches its `owned_files` lands reviewed, and the
consolidation completes instead of refusing on a window the flag itself never recorded.

**Why this priority**: this is the defect. Without it the flag is unusable on every Mission
it was built for.

**Independent Test**: drive the real `spec-kitty consolidate` (Typer command, `CliRunner`)
against a direct-on-target fixture with no `lanes.json` and assert exit 0 plus a recorded
merge baseline — the pre-existing red-first entry point in
`tests/specify_cli/cli/commands/test_issue_2745_merge_skip_lanes.py`.

**Acceptance Scenarios**:

1. **Given** a merge-ready direct-on-target Mission with no `lanes.json`, whose planning
   artifacts and work-package change are committed on the target branch, **When** the
   operator runs `consolidate --skip-lanes`, **Then** the run completes (exit 0, merge
   baseline recorded) instead of refusing `EVIDENCE_WINDOW_UNCOMPUTABLE`.
2. **Given** the same Mission run without `--skip-lanes`, **When** consolidation is
   attempted, **Then** it still hard-fails on the missing `lanes.json` — the flag, not some
   other change, is what unlocks completion.

---

### User Story 2 - An unresolvable window names a remedy that works (Priority: P2)

When the Mission's planning artifacts are not in the target branch's history at all, no
evidence window can be derived from history, and consolidation still refuses
`EVIDENCE_WINDOW_UNCOMPUTABLE`. The refusal must then name a remedy the operator can
actually perform in this topology — commit the Mission's planning artifacts on the target
branch — rather than pointing at `finalize-tasks`, which addresses a `lanes.json` that this
Mission does not have.

**Why this priority**: the issue asks for a working remedy in both outcomes, and a refusal
whose advice cannot succeed is a dead end even when the refusal is correct.

**Independent Test**: evaluate the evidence axis on a synthesized no-lane manifest whose
window cannot be resolved and assert the refusal names committing the Mission's planning
artifacts on the target branch, while still carrying the `EVIDENCE_WINDOW_UNCOMPUTABLE` code
that leads the line.

**Acceptance Scenarios**:

1. **Given** a direct-on-target Mission whose `kitty-specs/<slug>/` was never committed on
   the target branch, **When** the evidence axis judges an approved work package, **Then**
   the refusal leads with `EVIDENCE_WINDOW_UNCOMPUTABLE` and names committing the Mission's
   planning artifacts on the target branch as the remedy.

---

### User Story 3 - The evidence gates stay exactly as strict (Priority: P3)

Resolving a window must not relax what the axis proves. On the same synthesized window, a
work package whose change never touches its `owned_files`, or whose approval was recorded by
the implementer, is still refused with the same codes and the same strictness as a
`lanes.json` Mission.

**Why this priority**: the fix is about giving the axis a window, never about letting an
unreviewed or unimplemented work package through.

**Independent Test**: build the same direct-on-target fixture with a work package that owns
a path its window never changed, and assert `IMPLEMENTATION_MISSING`; and with an approval
recorded by the implementer, and assert `REVIEW_NOT_INDEPENDENT`.

**Acceptance Scenarios**:

1. **Given** a resolved synthesized window and an approved work package whose `owned_files`
   are untouched by it, **When** evidence is judged, **Then** the run refuses
   `IMPLEMENTATION_MISSING` — no attestation is introduced for the window and none lifts it.
2. **Given** a resolved synthesized window and an approval recorded by the same identity
   that claimed the work package, **When** evidence is judged, **Then** the run refuses
   `REVIEW_NOT_INDEPENDENT`.

---

### Edge Cases

- **The mission's first commit also carries code.** The resolved base is the target tip
  *immediately before* the first commit that introduced `kitty-specs/<slug>/`, so a first
  commit that carries planning artifacts and a work-package change together still yields a
  non-empty window.
- **The first commit that introduced the mission directory is the repository root commit.**
  It has no parent, so the commit itself is the base and the window is non-empty by
  construction.
- **The mission directory is committed on a coordination branch, not the target.** No base
  is resolvable from target history; the refusal path of User Story 2 applies and nothing is
  fabricated.
- **`target_override` (`--target`) is in force.** The window is resolved against the branch
  the run will actually merge into.
- **A `lanes.json` is present.** The synthesized-manifest path is not taken at all; recorded
  `planning_commit_sha` behaviour is byte-for-byte unchanged.
- **History cannot be read** (git probe error). Unresolvable, never a silently empty window.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Synthesized manifest records an evidence-window base | As an operator running `consolidate --skip-lanes` on a direct-on-target Mission, I want the synthesized `LanesManifest` to record a base commit the evidence window can use, so that an approved work package's change is actually judged instead of refused as uncomputable. | High | Open | [build] | no — a no-op leaves `planning_commit_sha` unset and the mission keeps refusing |
| FR-002 | Base is derived from target history, never fabricated | As a maintainer, I want the base resolved from the target branch's own history (the target tip immediately before this Mission's planning artifacts appeared), so that the window is reproducible and provable rather than invented. | High | Open | [build] | no — a no-op fabricates nothing but proves nothing; the row names a concrete resolved SHA |
| FR-003 | Unresolvable base leaves the refusal honest and actionable | As an operator whose Mission artifacts are absent from target history, I want `EVIDENCE_WINDOW_UNCOMPUTABLE` to name a remedy that works in a no-`lanes.json` Mission, so that the refusal is not a dead end. | Medium | Open | [build] | yes — paired with FR-001's completion row on the same fixture family, which proves the window is resolvable when history is present |
| FR-004 | Evidence and independence gates keep refusing | As a maintainer, I want `IMPLEMENTATION_MISSING` and `REVIEW_NOT_INDEPENDENT` to keep refusing through the synthesized window exactly as through a recorded one, so that no gate is weakened by this fix. | High | Open | [ratchet] | yes — paired with FR-001's positive completion on the same fixture, which proves the same window passes a work package that does own a changed path |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Bounded git cost | The synthesized manifest resolution adds at most two git invocations per `consolidate --skip-lanes` run (one history read for the Mission directory, one parent read), and none when a `lanes.json` is present. | Performance | Medium | Open |
| NFR-002 | Deterministic base | For one repository state the resolved base is the same commit on every run; it is a commit that exists on the target branch, not a timestamp or a generated id. | Reliability | High | Open |
| NFR-003 | Fail closed | Any git error during resolution yields "no base" (the existing refusal path), never an empty window that would pass every work package. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Own seam | Product code changes stay in `src/specify_cli/consolidation/` (`entry_preflight` synthesis and the `wp_evidence` refusal text); the coordination-teardown seam of #7198/#7199 is out of scope. | Technical | High | Open |
| C-002 | No `lanes.json` schema change | The recorded `planning_commit_sha` field and its persistence path are unchanged; only the in-memory synthesized manifest is populated. | Technical | High | Open |
| C-003 | Opt-in unchanged | `--skip-lanes` stays an explicit opt-in; a Mission with a `lanes.json` never takes the synthesized path. | Business | High | Open |

### Key Entities

- **Synthesized no-lane manifest**: the in-memory `LanesManifest` built when `--skip-lanes` is
  given and no `lanes.json` exists. Gains an evidence-window base commit resolved from the
  target branch's history.
- **Evidence window**: `base..tip`, a tree diff, judged per approved work package against its
  authored `owned_files`.
- **Mission start boundary**: the target-branch commit immediately before the first commit
  that introduced `kitty-specs/<slug>/` — the point this Mission's planning began.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The three `--skip-lanes` nodes in `tests/specify_cli/cli/commands/test_issue_2745_merge_skip_lanes.py` pass on the fixed tree (they refuse `EVIDENCE_WINDOW_UNCOMPUTABLE` on `origin/main` before the change) — [build] · no-op passable: no
- **SC-002**: A `consolidate --skip-lanes` run on a direct-on-target Mission records a merge baseline and advances the target ref, and the same Mission without the flag still refuses on the missing `lanes.json` — [build] · no-op passable: no
- **SC-003**: An approved work package whose window shows no change to its `owned_files` still refuses `IMPLEMENTATION_MISSING` on the synthesized window — [ratchet] · no-op passable: yes — paired with SC-001's completion row on the same fixture family
- **SC-004**: The `EVIDENCE_WINDOW_UNCOMPUTABLE` refusal for an unresolvable base names committing the Mission's planning artifacts on the target branch — [build] · no-op passable: no
