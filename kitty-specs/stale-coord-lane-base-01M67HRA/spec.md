# Mission Specification: Stale coord lane base

**Mission Branch**: `issue-6753-stale-coord-lane-base`
**Created**: 2026-10-30
**Status**: Draft
**Input**: spec-kitty/spec-kitty#6753 — "coord topology silently cuts a fresh lane from a coordination branch that has fallen behind the target branch"

## Intent Summary

- **Primary actor:** an agent (or the operator) starting a code work package on a
  coordination-topology Mission, through the documented path — `spec-kitty next`,
  `spec-kitty agent action implement <WP>`, or the `/spec-kitty.implement` shim.
- **Trigger:** a fresh lane allocation on a Mission whose coordination branch no
  longer contains the target branch tip, because the target advanced after the
  coordination branch was minted (typically a reviewed prerequisite PR merged to
  the target).
- **Desired outcome:** the stale base is *visible at allocation time*. The
  allocator names the coordination branch, the target branch and the target
  commit the lane does not contain, and names the remedy; the documented agent
  path can then act on that remedy because it accepts `--base`.
- **Rule that must always hold:** a fresh lane cut with no explicit `base` still
  parents on the coordination branch (C-005 / FR-006 of the lane-base mission —
  byte-identical legacy behaviour). This Mission does not dispute that default;
  it removes the *silence*, not the default.
- **Boundaries:** no change to `_resolve_lane_parent`'s topology-derived parent,
  no automatic re-parenting or automatic merge of the target into the
  coordination branch or the lane, no new refusal route in the allocator, no
  legacy-topology (single-branch / no-`coordination_branch`) behaviour change.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A stale coordination branch is reported, never silent (Priority: P1)

An agent starts the first code work package of a coordination-topology Mission.
The coordination branch was minted from the target branch at mission creation and
the target has since advanced. Today the lane is cut from the stale coordination
branch and nothing says so; the gap only shows up later, as a missing
prerequisite in the lane's tree. After this Mission the same allocation prints a
warning that names the coordination branch, the target branch, the target commit
the lane does not contain, and the command that cuts the lane from the target
tip instead.

**Why this priority**: this is the defect in the issue. Everything else is the
remedy the warning points at.

**Independent Test**: build a repository with a coordination branch, advance the
target branch past it, allocate a fresh lane for a code work package, and read
the allocation's output; then re-run the same fixture with the coordination
branch holding the target tip and confirm the warning is absent.

**Acceptance Scenarios**:

1. **Given** a coordination-topology Mission whose coordination branch does not
   contain the target tip, **When** a fresh lane is allocated with no explicit
   base, **Then** the allocation prints exactly one stale-base warning naming the
   coordination branch, the target branch, the target tip commit and the
   `--base` remedy, and the lane is still parented on the coordination branch.
2. **Given** the same fixture with the coordination branch containing the target
   tip, **When** a fresh lane is allocated, **Then** no stale-base warning is
   printed (positive control on the same fixture).
3. **Given** the target branch cannot be resolved, **When** a fresh lane is
   allocated, **Then** the probe stays silent and allocation proceeds exactly as
   today (a probe that cannot answer must never block or invent a warning).

---

### User Story 2 - The documented agent path can act on the remedy (Priority: P1)

The path `next` and the `/spec-kitty.implement` shim dispatch is
`spec-kitty agent action implement <WP> --agent <name>`. Today only the internal
top-level `spec-kitty implement <WP> --base <ref>` accepts an explicit base, so an
agent following the documented loop cannot act on the remedy the warning names.
After this Mission `agent action implement` accepts `--base` and honours it on a
fresh lane, exactly as the top-level command does.

**Why this priority**: without it the warning is unactionable from the path the
documentation tells agents to use, which is the second half of the issue.

**Independent Test**: run `spec-kitty agent action implement <WP> --agent <name>
--base <target>` against a coordination-topology Mission whose target has
advanced, and check that the created lane branch contains the target tip commit
and the prerequisite file the target added.

**Acceptance Scenarios**:

1. **Given** a coordination-topology Mission whose target advanced, **When**
   `agent action implement` is run with `--base <target>`, **Then** the lane
   branch contains the target tip commit and no stale-base warning is printed.
2. **Given** the same Mission, **When** `agent action implement` is run without
   `--base`, **Then** the lane parents on the coordination branch and the
   stale-base warning is printed — the pre-#6753 default parentage is unchanged.

---

### User Story 3 - Unrelated base-refusals keep their semantics (Priority: P2)

An operator supplies `--base` on a route that cannot be re-parented (an existing
lane worktree, a surviving branch in crash recovery, a dependency-bearing lane,
or a base detached from the recorded planning commit). The existing
`UnhonorableBaseError` refusals still fire, unchanged, and stay reachable through
both the top-level command and `agent action implement`.

**Why this priority**: threading a new option through a second entry point is
exactly where a refusal route can get lost.

**Independent Test**: drive `agent action implement --base` over a lane that
already exists and confirm the same structured refusal the top-level command
raises.

**Acceptance Scenarios**:

1. **Given** an already-allocated lane, **When** `agent action implement` is run
   with `--base`, **Then** it refuses with the reuse-route `UnhonorableBaseError`
   message and creates nothing.

### Edge Cases

- **Explicit base that is already correct**: `--base <target>` on a stale
  coordination branch prints no stale-base warning (the lane *does* contain the
  target tip), even though the default topology parent would be stale.
- **Explicit base that is also stale**: an explicit `base` that does not contain
  the target tip still warns; the warning describes the ref the lane was
  actually cut from, not the coordination branch specifically.
- **Legacy topology** (no `coordination_branch` in `meta.json`): no probe, no
  warning — that path creates the mission branch from the target branch when it
  is missing and is out of scope here.
- **Reuse and crash recovery**: an existing lane is not re-cut, so no stale-base
  warning is emitted; the fresh cut is the decision point this Mission
  instruments.
- **Planning (repository-root) lane**: `--base` remains ignored with the
  existing warning; unchanged behaviour.
- **Target branch unresolved** (detached HEAD on a missing ref, or a
  non-`git` fixture path): the probe degrades to silence; allocation behaviour is
  byte-identical to today.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Report a stale coordination branch at fresh lane allocation | As an agent starting a code WP on a coord-topology Mission, I want a fresh lane allocation to tell me when the lane's base does not contain the target branch tip, naming both refs, the missing target commit and the remedy, so that a lane is never silently cut behind the target (#6753). | High | Open | [build] | no |
| FR-002 | Stay silent when the base is current | As an agent, I want no stale-base warning when the ref the lane is cut from already contains the target tip, so that the warning means something when it appears. | High | Open | [ratchet] | yes — paired with FR-001 on one shared fixture (same repo, target advanced vs not) |
| FR-003 | Keep the topology-derived parent | As a maintainer, I want a fresh lane with no explicit `base` to keep parenting on the coordination branch, so that C-005 / FR-006's byte-identical legacy behaviour is preserved. | High | Open | [ratchet] | yes — paired with FR-001's stale scenario, which asserts the parent is still the coordination branch while the warning fires |
| FR-004 | Accept `--base` on `agent action implement` | As an agent following the documented loop, I want `spec-kitty agent action implement` to accept the explicit base that `resolve_lane_base_or_refuse` already honours on fresh routes, so that the dispatched path can act on the remedy (#6753). | High | Open | [build] | no |
| FR-005 | Keep the base-refusal routes intact | As an operator, I want the reuse, crash-recovery, dependency-lane and detached-base refusals to keep firing identically through `agent action implement`, so that the new option cannot buy silent no-ops. | Medium | Open | [ratchet] | yes — paired with FR-004's honoured-base scenario on the same fixture |
| FR-006 | Never refuse on a stale base | As a maintainer, I want the stale-base condition to inform, not block, so that a coord-topology Mission whose target advanced (the normal case on a busy target branch) is not turned into a hard stop for every fresh lane. | High | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Status |
|----|-------|-------------|----------|--------|
| NFR-001 | Probe cost | The stale-base probe adds at most one `git merge-base --is-ancestor` invocation per fresh coord-topology lane allocation, and none on the reuse, crash-recovery, legacy or planning-lane routes. | Performance | Open |
| NFR-002 | Fail-safe probe | A probe that cannot answer (unresolvable target tip, git failure, non-git path) never raises and never changes allocation's outcome: it emits nothing and allocation proceeds exactly as before. | Reliability | Open |
| NFR-003 | Message completeness | The warning text contains the coordination branch name, the target branch name, a concrete commit id present on the target and absent from the base, and a runnable command carrying the WP id — all four, on one line group, at 100% of emissions. | Usability | Open |

### Constraints

| ID | Title | Constraint | Category | Status |
|----|-------|------------|----------|--------|
| C-001 | Default parent unchanged | `_resolve_lane_parent` keeps returning the coordination branch when `base is None`; this Mission instruments the stale case and never re-parents it (#6753 "does not dispute the default"). | Technical | Open |
| C-002 | Warn, do not refuse | A stale coordination branch is reported; it is never turned into a new `StructuredError`/refusal route. The issue permits warn or refuse; warn is chosen and pinned by tests because a refusal would block every coord Mission whose target advanced. | Technical | Open |
| C-003 | One new option only | The only new CLI surface is `--base` on `agent action implement`, mirroring the existing top-level `spec-kitty implement --base` help text and semantics. | Technical | Open |
| C-004 | Existing output convention, on the diagnostic channel | The warning uses the module's existing `WARNING: ...` convention, emitted on **stderr** — not stdout and not a new logging channel. Amended during implementation after the review found that `spec-kitty implement --json` keeps stdout for its machine-readable payload and `_json_safe_output` captures only the rich console, so a stdout warning would prepend a line to the JSON on the common stale-coord cut. | Technical | Open |
| C-005 | No automatic history changes | Neither the coordination branch nor the lane is merged, rebased or fast-forwarded by this Mission; only probing, reporting and the explicit operator-supplied base. | Technical | Open |

### Key Entities

- **Stale-base probe**: the read-only comparison of the target branch tip against
  the ref a fresh lane is cut from. Answers "current" / "stale" / "unknown".
- **Fresh lane allocation**: `allocate_lane_worktree`'s FRESH_COORD route — the
  single point where a lane's parent ref is decided and a worktree is created.
- **Remedy command**: the `--base <target>` invocation the warning names, which
  FR-004 makes reachable from the dispatched agent path.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the #6753 reproduction (coordination branch minted, target advanced, fresh coord lane allocated with no base), the run prints one warning containing the coordination branch, the target branch, the missing target commit id and the `--base` remedy, in 100% of runs. — [build] · no-op passable: no
- **SC-002**: On the same fixture with the coordination branch holding the target tip, zero stale-base warnings are printed across 100% of fresh allocations. — [ratchet] · no-op passable: yes — paired with SC-001 on the same fixture
- **SC-003**: `spec-kitty agent action implement <WP> --base <target>` produces a lane branch for which `git merge-base --is-ancestor <target-tip> <lane>` exits 0, verified end to end through the CLI. — [build] · no-op passable: no
- **SC-004**: Every existing lane-allocation refusal route (reuse, crash recovery, dependency lane, detached base) still raises its structured error unchanged, with zero regressions in the lanes test suites. — [ratchet] · no-op passable: yes — paired with SC-003's honoured-base scenario (the same plumbing change must not swallow either side)
