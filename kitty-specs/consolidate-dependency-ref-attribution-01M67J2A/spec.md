# Mission Specification: Consolidate dependency-ref attribution (#6771)

**Mission Branch**: `issue-6771-consolidate-dependency-ref-attribution`
**Created**: 2026-10-30
**Status**: Draft
**Input**: spec-kitty/spec-kitty#6771 — "consolidate --strategy merge refuses a mission whose lane merged its updated dependency branch (closed-world flags every second-parent commit as un-attributable); --dry-run passes"

## Problem

A mission built on another in-flight branch has to pick up that branch's newer head
before landing. The supported way to do that without rewriting reviewed commits is a
two-parent merge inside a WP lane (`git merge --no-ff <dep-new>`), after which the lane is
reviewed and approved on the merged tree. `spec-kitty consolidate --strategy merge` then
lands the mission, runs reconciliation, and the closed-world attribution axis
(`MergeOutcomeVerifier._unattributable_content`) reports every content commit the merge's
second parent brought in as "un-attributable (removed/canceled work would ship)", and the
run rolls back — correctly, but the work is legitimate. `--dry-run` exits 0 beforehand and
reports nothing, because the forecast terminates before reconciliation runs. The two
surfaces disagree, and there is no supported way to restack a mission onto an updated
dependency branch and still consolidate it.

Verified on current `main` (512567eee7): a lane that merges an external branch
(`src/dep/*`, three commits) is approved on that tree, `consolidate --strategy merge
--dry-run` exits 0, and `consolidate --strategy merge` exits 1 naming the dependency's
commits as un-attributable.

## Terms

- **Dependency ref** — a git ref outside the mission (a branch, tag or SHA the mission was
  built on) whose newer head a lane merged in. NOT a mission lane, and NOT the mission's
  own coordination branch.
- **Closed-world window** — `excluded_window_base..target`, the commits the consolidation
  landed; every *content* commit in it must be attributable to an approved WP.
- **Attributable** — authored by an approved WP's own first-parent spine (SHA or patch-id),
  under squash also by final per-path blob.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A lane's merged dependency branch is not "removed work" (Priority: P1)

An operator restacks a mission onto a newer dependency head by merging that head into the
lane that depends on it, has the lane re-reviewed on the merged tree, and consolidates with
`--strategy merge`. They declare the dependency ref to `consolidate`; the run lands, and
reconciliation treats the dependency's commits as inherited history rather than as work the
mission removed.

**Why this priority**: This is the reported refusal; without it the mission cannot land.

**Independent Test**: The real-CLI repro (`build_coord_mission`, an external branch with
content commits merged into WP02's lane, `restamp_approvals_at_lane_tips`), run with
`consolidate --strategy merge --dependency-ref <ref>`: exit 0, the dependency content and
the lane content both reach the target.

**Acceptance Scenarios**:

1. **Given** an approved lane whose head is a two-parent merge of an external dependency
   branch, **When** `consolidate --strategy merge --dependency-ref <ref>` runs, **Then** it
   exits 0 and reconciliation passes.
2. **Given** the same mission, **When** `consolidate --strategy merge` runs with no
   declaration, **Then** the closed-world axis still refuses (unchanged fail-closed
   behavior).
3. **Given** the same mission and a declaration naming a ref that is not the merged-in
   dependency (an unrelated branch, or a ref that does not resolve), **When** the run
   starts, **Then** it refuses before any ref moves and names the ref and the reason.

---

### User Story 2 - `--dry-run` predicts the closed-world refusal (Priority: P1)

An operator runs `--dry-run` before the real run. The forecast evaluates the same
closed-world window against the content the landing would introduce, so a refusal is
predictable before any ref moves, and the forecast and the real run agree.

**Why this priority**: The issue names the disagreement as the defect: a preflight that
passes where the run fails is worse than either alone.

**Independent Test**: On the repro mission, `--dry-run` exits non-zero and names the
un-attributable commits; with `--dependency-ref` added, `--dry-run` exits 0 and the real
run that follows also exits 0.

**Acceptance Scenarios**:

1. **Given** a mission whose lane merged an undeclared external branch, **When**
   `consolidate --strategy merge --dry-run` runs, **Then** it exits non-zero, names the
   un-attributable commits, and points at the declaration that resolves it.
2. **Given** the same mission with the dependency ref declared, **When** `--dry-run` runs,
   **Then** it exits 0 and the subsequent real run exits 0 (the two agree).
3. **Given** a mission with no external content in the window, **When** `--dry-run` runs,
   **Then** it exits 0 exactly as it does today (no new false refusal).

---

### User Story 3 - Genuine un-attributable detection is not loosened (Priority: P1)

A maintainer relies on the closed-world axis to catch removed/canceled work riding a
carrier lane. Declaring a dependency ref must not create a bypass: no mission-authored
commit — on any lane's first-parent spine, the mission branch or the coordination branch —
can ever be exempted by a declaration.

**Why this priority**: The axis exists to stop silent data loss (#4945/#4977/#4981); a fix
that widens it into a bypass is worse than the bug.

**Independent Test**: A canceled WP's commit planted on its own lane branch, declared as a
dependency ref, is refused at claim time (the declaration is rejected, and the smuggled
commit stays un-attributable with no declaration); the #4945/#5013 repros stay green.

**Acceptance Scenarios**:

1. **Given** a declared ref whose commits include any commit on a mission spine, **When** a
   consolidation runs, **Then** it REFUSEs, naming the offending commit and the spine.
2. **Given** a removed WP's commit carried by an approved lane and no declaration, **When**
   the run reaches reconciliation, **Then** it still FAILs as un-attributable.

### Edge Cases

- The declaration names a ref already reachable from the target's pre-run tip: nothing in
  the window is exempted, so the run behaves as if it were not declared (no refusal, no
  widening).
- The declaration names a ref the mission branch does not reach (never merged in): it is a
  mis-declaration and is refused rather than silently ignored.
- The window base cannot be resolved while a declaration is in force: REFUSE (fail-closed),
  never evaluate the closed world on an unbounded window.
- A hand-built claim (tests that populate only `approved`) has no declaration and keeps the
  pre-existing behavior byte-for-byte.
- Several dependency refs declared at once: each is verified independently; one bad
  declaration refuses the run.
- Squash strategy: the same declaration exempts the dependency's final per-path blobs from
  the squash blob-attribution axis, so the class is closed under both strategies.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Declared dependency refs exempt | As an operator, I want to declare the dependency ref a lane merged in so that its commits are inherited history, not removed work. | High | Open | [build] | no — the repro exits 1 without the declaration and 0 with it |
| FR-002 | Declaration verified fail-closed | As a maintainer, I want every declaration verified against the repository so that a mis-declaration refuses instead of silently widening attribution. | High | Open | [build] | no — an unresolvable or never-merged ref refuses |
| FR-003 | No mission commit is exemptible | As a maintainer, I want a declaration that covers any commit on a mission spine refused, so the closed world cannot be bypassed. | High | Open | [ratchet] | no — same fixture, opposite verdicts with and without spine overlap |
| FR-004 | Dry-run runs the closed-world window check | As an operator, I want `--dry-run` to report the closed-world refusal so that the preflight and the real run agree. | High | Open | [build] | no — the repro's dry-run exits 1 before the fix and 0 after |
| FR-005 | Declaration reaches both surfaces | As an operator, I want `--dependency-ref` honoured by the forecast and the real run alike so that a green forecast means a landing run. | High | Open | [build] | no — dry-run and real run are asserted on the same declaration |
| FR-006 | Squash axis honours the declaration | As an operator, I want the declaration to cover the squash blob axis too so that the same restack works under either strategy. | Medium | Open | [build] | no — a squash landing of the same repro is asserted |
| FR-007 | Refusal names the recovery | As an operator, I want the un-attributable refusal to name the commits and the declaration that resolves it so that the fix is discoverable from the error. | Medium | Open | [build] | no — the refusal text is asserted |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Window-scoped cost | An undeclared run adds exactly zero git probes. A declared run adds only window-bounded ranges: one `<window_base>..<ref>` per declared ref, one first-parent range per lane and for the mission branch (the spine guard), never a full-history scan. | Performance | High | Open |
| NFR-002 | Fail-closed on probe error | Any git probe failure while resolving or verifying a declaration is a REFUSE, never a PASS. | Reliability | High | Open |
| NFR-003 | No behaviour change without a declaration | With no `--dependency-ref`, the constructed claim and every verdict are identical to today's (pinned by the existing suite). | Compatibility | High | Open |
| NFR-004 | Deterministic refusal text | The same repository state produces the same refusal text and exit code on the forecast and on the real run. | Reliability | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| C-001 | No merge-simulation widening | The fix must not widen the attribution recognizer toward simulating merges (`_final_authored_walk` docstring: restore write-scope disjointness upstream instead). Attribution is either an approved lane's own authorship or an explicitly declared, verified external ref. | Technical | High | Open |
| C-002 | Single canonical authority | The exemption is computed once, in the claim builder, and threaded to both the verifier and the forecast; no second copy of the spine/attribution rules. | Technical | High | Open |
| C-003 | Closed world stays closed | An undeclared run keeps today's verdicts; the declaration only ever narrows what is flagged, never widens what is attributed to a WP. | Technical | High | Open |

### Key Entities

- **Declared dependency ref**: an operator-supplied git ref; verified to resolve, to be
  reached by the mission branch, and to contribute no commit on any mission spine.
- **Exempt commit set**: the declared refs' commits inside the closed-world window; treated
  exactly like commits already on the target before the run.
- **Exempt blob/deletion set**: the declared refs' final per-path state, for the squash axis.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The reported repro (external branch merged into a lane, `--strategy merge`) consolidates at exit 0 when the dependency ref is declared, and at exit 1 when it is not. — [build] · no-op passable: no
- **SC-002**: `--dry-run` and the real run return the same verdict and exit code on that repro, with and without the declaration (4 of 4 matching). — [build] · no-op passable: no
- **SC-003**: The #4945/#5013 removed-WP repros and the existing consolidation suite are unchanged (0 new failures). — [ratchet] · no-op passable: no
- **SC-004**: A declaration covering any mission-spine commit is refused (100% of the declared spine-overlap cases covered by tests). — [ratchet] · no-op passable: no
