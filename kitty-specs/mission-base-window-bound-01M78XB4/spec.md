# Mission Specification: Bound reconciliation windows at the Mission base (#7560)

**Mission Branch**: `kitty/mission-mission-base-window-bound-01M78XB4`
**Created**: 2026-11-12
**Status**: Draft
**Input**: Issue #7560 (P1, parent #7358), the reproduction in its second report, and the operator rulings recorded as Decision Moments `01M78XBQS8NE8PPMSTZHMDJ610`, `01M78XBWYTWJ6TZJVF4GWQMCQF`, `01M78XC2CJVH9ZXR0WB92NWYG5` and `01M78XC76BMN026BTEH4T1ADFM`.
**Research**: [`research/code-grounding.md`](research/code-grounding.md), [`research/foldable-issues.md`](research/foldable-issues.md)

## Intent Summary (confirmed by operator rulings)

- **Primary actor:** a maintainer of a fork who runs `spec-kitty consolidate` on an integration Mission.
- **Trigger:** the local target branch does not contain the commit the Mission branch was cut from. For example, the Mission was started from an upstream pin plus an overlay, or from a `--pr-bound` start branch the local target lacks.
- **Desired outcome:** history from before the Mission was created is never treated as Mission work, on any reconciliation axis. Report 1 consolidates with `--strategy merge --dependency-ref U`; report 2 consolidates without phantom un-attributable content.
- **Rule that must always hold:** every commit the Mission authored or carried after its base keeps refusing exactly as today. That covers commits on the Mission branch after the base, lane spines, `lane_head` stamps and recorded lane tips.
- **Canonical terms:** *Mission base*, the commit the Mission branch was cut from (it is never the "claim base", which is a different authority); *window base*, the target's pre-run tip; *declared dependency ref* (#6771).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Declared upstream refresh consolidates (Priority: P1)

A fork maintainer's Mission merges an upstream commit `U` into a lane. The local target is missing upstream history that sits below the Mission base. They run `consolidate --strategy merge --dependency-ref U`.

**Why this priority**: it is report 1. Today it refuses with `DEPENDENCY_REF_COVERS_MISSION_WORK`, and there is no workaround.

**Independent Test**: a fixture with that shape; `--dry-run` and the real run.

**Acceptance Scenarios**:

1. **Given** the report-1 shape, **When** the maintainer runs `consolidate --strategy merge --dependency-ref U --dry-run`, **Then** no `DEPENDENCY_REF_COVERS_MISSION_WORK` is raised for a commit below the Mission base, and the forecast passes.
2. **Given** the same shape, **When** the real run executes, **Then** it lands and the reconciliation gate passes.

### User Story 2 - Mission started on top of the target's missing history (Priority: P1)

A Mission is cut from an upstream pin plus a fork overlay commit, and the local target never received either. There is no upstream merge inside a lane.

**Why this priority**: it is report 2. Both the plain run (phantom un-attributable content and deletions) and the declared run (`DEPENDENCY_REF_COVERS_MISSION_WORK` naming the base's parent) refuse.

**Independent Test**: the reproduced report-2 fixture, with plain and declared `--dry-run` and the real run.

**Acceptance Scenarios**:

1. **Given** the report-2 shape, **When** plain `consolidate --dry-run` runs, **Then** no commit, blob or deletion that is reachable from the Mission base is reported as un-attributable.
2. **Given** the same shape, **When** `--dependency-ref <pin>` is declared, **Then** the guard does not name the pin or any other pre-base commit as Mission work.

### User Story 3 - Genuine Mission work keeps refusing (Priority: P1)

An operator tries to use the fix as a bypass. They declare a ref that reaches a commit the Mission authored after its base, or the Mission carries un-attributable content after its base.

**Why this priority**: soundness. This is the reason the guard exists.

**Independent Test**: the same fixtures with a post-base commit on the Mission branch, a lane spine commit, a `lane_head` stamp and a recorded lane tip.

**Acceptance Scenarios**:

1. **Given** a declared ref that reaches a post-base Mission-branch commit, **When** the claim is built, **Then** it refuses with `DEPENDENCY_REF_COVERS_MISSION_WORK`.
2. **Given** an un-attributable post-base commit on a lane, **When** the gate runs, **Then** it fails exactly as today.

### User Story 4 - Base provenance is visible (Priority: P2)

The maintainer can see whether the Mission base was recorded, derived, or unavailable. When it is unavailable, the run falls back to today's bound.

**Acceptance Scenarios**:

1. **Given** a Mission created before this change, **When** consolidate runs, **Then** it derives the base and says that it did.
2. **Given** a Mission whose base cannot be derived, **When** consolidate runs, **Then** it uses today's bound and prints a note naming the reason.

### Edge Cases

- A recorded base that is no longer an ancestor of the Mission branch (the branch was rebased or rewritten) is not used. The derivation is tried next, and it validates its own answer the same way; if neither yields a valid base, the base is unavailable and today's bound applies (fail-closed). The note says why.
- The scaffold commit was skipped, merged in through a second parent, or committed on the target before the Mission branch was minted. In each case the derivation yields no answer, or a target-reachable commit, and changes nothing.
- The local target already contains the base, which is the common, non-fork case: every verdict stays byte-identical to today.
- `--resume` uses the base that the interrupted run claimed with, never a value recomputed after a mutation.
- A declared ref that lies entirely below the Mission base exempts nothing new, because that history is already outside every window.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Record the Mission base | As a maintainer, I want the commit my Mission branch is cut from to be recorded when the Mission is created or minted, so that consolidation has an authority for it. | High | Open | [build] | no |
| FR-002 | One Mission-base authority | As a maintainer, I want one resolver that yields the Mission base and its provenance, so that every window uses the same lower bound. Provenance is `recorded`, else `derived` (first parent of the earliest first-parent commit on the Mission branch that adds `kitty-specs/<slug>/`), else `unavailable`. A base that is not an ancestor of the Mission branch counts as unavailable. | High | Open | [build] | no |
| FR-003 | Guard bounded at the base | As a fork maintainer, I want the #6771 Mission-spine walk and the recorded-tip walk to exclude ancestors of the Mission base, so that a declared upstream ref is not refused for pre-Mission history. The declared ref's own window stays `target..ref`. | High | Open | [build] | no — paired with FR-005 on the same fixture |
| FR-004 | All window axes bounded at the base | As a fork maintainer, I want the closed-world scan (fresh run, gate and forecast), the squash blob and deletion axes and the patch-id window to treat history reachable from the Mission base as predating the window (the approved-bound and canceled-content axes are unchanged, per the dispatch non-goal; they never see pre-base commits), so that pre-Mission content is never reported as un-attributable. | High | Open | [build] | no — paired with FR-005 on the same fixture |
| FR-005 | Genuine Mission work still refuses | As a reviewer, I want commits after the Mission base to keep their current verdicts on every axis, so that the fix cannot be used as a bypass. That covers Mission-branch commits, lane spines, `lane_head` stamps, recorded tips and un-attributable post-base content. | High | Open | [ratchet] | yes — positive control is FR-003/FR-004 on the same fixture |
| FR-006 | Same base on every route | As a maintainer, I want `--dry-run`, the fresh run, the gate re-check and `--resume` to use the same Mission base, so that the forecast predicts the real run. | High | Open | [build] | no |
| FR-007 | Provenance reported | As a maintainer, I want consolidation to say when the base was derived or unavailable, so that I know which bound judged my landing. | Medium | Open | [build] | no |
| FR-008 | Decision recorded | As a reviewer, I want ADR `2026-09-29-1` to carry an amendment that states the Mission-base lower bound, so that the verdict change is governed. | Medium | Open | [build] | no |
| FR-009 | Stamp read pin (#7593) | As a maintainer, I want an architectural gate pinning that consolidation reads commit-to-target stamps only through `consolidation_events`. This is blocked until PR #7596 merges, and is delivered only once it has. | Low | Blocked | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No new cost when the base is reachable | When the target's pre-run tip already reaches the Mission base, verdicts are byte-identical to today's on the existing `tests/consolidation` suite: 0 changed expectations. | Reliability | High | Open |
| NFR-002 | Bounded extra probes | Resolving the base adds at most 3 git invocations per consolidate run. | Performance | Medium | Open |
| NFR-003 | Fail-closed | Every probe error while resolving the base yields `unavailable` (today's bound), never a wider exemption: 100% of injected probe failures in tests. | Security | High | Open |
| NFR-004 | Quality gates | New code passes `ruff`, `ruff format`, `mypy`; no function above complexity 15; diff coverage at or above 90%. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No refusal-code changes | No refusal code, exit code or gate severity changes. A new note line is allowed; a new refusal code is not. | Technical | High | Open |
| C-002 | One rollback authority | No second rollback path; `test_single_rollback_authority.py` stays green. | Technical | High | Open |
| C-003 | Stay off A2's surfaces | Do not touch consolidate recovery, teardown, resume or refusal text (#7598). | Process | High | Open |
| C-004 | No pack edits, no size gates | No edits under `packs/built-in`; no new size or ratchet gates. | Process | High | Open |
| C-005 | Facade compatibility | Names moved or added in `reconciliation_*.py` stay reachable through the `reconciliation.py` facade. | Technical | Medium | Open |

### Key Entities

- **Mission base**: the commit the Mission branch was cut from. Its provenance is one of `recorded`, `derived` or `unavailable`.
- **Window base**: the target's pre-run tip; unchanged.
- **Window**: commits reachable from the landing ref and from neither the window base nor the Mission base.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The report-1 and report-2 shapes consolidate (dry run and real run) with 0 refusals for pre-base history — [build] · no-op passable: no
- **SC-002**: 100% of the post-base Mission-work cases listed in User Story 3 still refuse with their current codes — [ratchet] · no-op passable: yes (paired with SC-001 on the same fixtures)
- **SC-003**: 0 changed verdicts on existing consolidation tests where the target reaches the base — [ratchet] · no-op passable: yes (paired with SC-001)
- **SC-004**: An existing Mission (no recorded base) is unblocked without any manual step — [build] · no-op passable: no

## Assumptions

- Pre-base history the target lacks (upstream commits or a fork overlay) is content the operator chose to build on. Landing it without a work package attributing it is accepted policy, per operator ruling `01M78XC2CJVH9ZXR0WB92NWYG5`.
- A derived base reads history the operator can edit. Editing it is a recorded operator act, and the ADR amendment says so.
