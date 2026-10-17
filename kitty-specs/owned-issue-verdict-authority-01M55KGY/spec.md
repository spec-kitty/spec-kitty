# Mission Specification: Owned issue-verdict authority

**Mission Branch**: `owned-issue-verdict-authority-01M55KGY`
**Created**: 2026-10-17
**Status**: Draft
**Input**: Issue #6320 — `agent mission issue-verdict` loses owned authority for owned-only missions (twin of #6023).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Record a criterion verdict in an owned-only mission (Priority: P1)

An operator (or agent) runs an owned-only, PR-bound `single_branch` mission whose
`kitty-specs/<slug>/` and `meta.json` live only in the owned checkout `P`, not in the
repository root checkout `R`. During review they need to record an issue-matrix verdict for
a GitHub issue the mission cites, using `spec-kitty agent mission issue-verdict
--owned-checkout P`. Today the command resolves the mission from `R`, fails to find it, and
its fail-closed write-target gate refuses — so the verdict can never be recorded and the
owning work package can never be approved.

**Why this priority**: This is the headline defect of #6320. Without it an owned-only mission
cannot complete the review→approve path for any cited issue; it is the exact twin of the
#6023 acceptance-verdict gap, which was already fixed for the acceptance surface.

**Independent Test**: In an owned R/P/S fixture (reuse the #6023 owned fixtures), run
`issue-verdict --owned-checkout P` for a cited issue and assert the verdict lands in P's
`issue-matrix.json`. Red at merge-base (MISSION_NOT_FOUND / fail-closed refusal), green after.

**Acceptance Scenarios**:

1. **Given** an owned-only PR-bound `single_branch` mission present only in `P`, **When**
   `issue-verdict --owned-checkout P --issue <N> --verdict <v>` is run from `R` (or any cwd),
   **Then** the verdict is written to P's `issue-matrix.json` and the command exits success.
2. **Given** the same mission, **When** `issue-verdict` is run from inside `P` with **no**
   explicit `--owned-checkout`, **Then** flagless adoption resolves `P` and the verdict is
   recorded (mirror #6023 adoption).
3. **Given** an `--owned-checkout` path that does not resolve a real mission, **When**
   `issue-verdict` runs, **Then** it still refuses fail-closed (no silent fallback to `R`).

### User Story 2 - Owned coord-topology read resolves the right matrix (Priority: P2)

For an owned mission on a coordination topology, the issue-verdict read + legacy-migration
path must also carry the owned fact so it reads/migrates the matrix from the owned surface
rather than the repository root.

**Why this priority**: Confirmed in-scope by the operator's scope decision
(`include-coord-owned-read`). #6320's primary case is `single_branch` (where
`coord_read_dir_for` returns `None` and the owned write dir is what matters), but the read
path must not silently read `R` for an owned coord mission.

**Independent Test**: Owned coord fixture: assert `_resolve_read_dir` / `coord_read_dir_for`
/ `_migrate_if_needed` consume the owned fact and resolve the owned matrix dir.

**Acceptance Scenarios**:

1. **Given** an owned coord-topology mission, **When** issue-verdict resolves the read dir,
   **Then** the owned fact selects the owned matrix surface (not `R`).

### Edge Cases

- A legacy `.md` issue-matrix in the owned checkout is migrated from the owned surface, not `R`.
- The three unrelated callers of the shared write-target gate (decision-log default target,
  bookkeeping-commit target, status-transition write target) must behave identically — they
  pass no owned fact and must stay byte-identical.
- Ordinary repository-root and coordination issue-verdict (no `--owned-checkout`, mission in `R`)
  is unchanged.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Owned verdict recorded via `--owned-checkout` | As an operator of an owned-only mission, I want `issue-verdict --owned-checkout P` to write the verdict to P's issue-matrix so that a cited issue's owning work package can be approved. | High | Open | [build] | no |
| FR-002 | Fail-closed write-target gate is owned-aware | As an owned-mission user, I want `resolve_for_write` and the `mission_runtime` write-target gate to recognize my owned mission when given the owned fact so that the gate stops refusing a genuinely-present owned mission. | High | Open | [build] | no |
| FR-003 | Owned coord read + migration path carries the fact | As an owned coord-topology user, I want the read dir resolution and legacy-matrix migration to consume the owned fact so that the matrix is read/migrated from the owned surface, not the repository root. | Medium | Open | [build] | no |
| FR-004 | Flagless owned adoption records the verdict | As an agent working inside the owned checkout, I want `issue-verdict` with no explicit flag to adopt the owned checkout from cwd so that owned verdicts record without the flag (mirror #6023). | Medium | Open | [build] | no |
| FR-005 | Unrelated write-target-gate callers unchanged | As a maintainer, I want the three other callers of the shared write-target gate to stay byte-identical so that this fix does not perturb decision-log, bookkeeping-commit, or status-transition write targeting. | High | Open | [ratchet] | yes — paired with the owned positive case (FR-002) on the same gate fixture |
| FR-006 | Repo-root / coordination verdict unchanged | As an ordinary user, I want repository-root and coordination issue-verdict (no `--owned-checkout`) to behave exactly as before so that the owned thread-through is purely additive. | Medium | Open | [ratchet] | yes — paired with the owned positive case (FR-001) on the same command fixture |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Fail-closed preserved | An owned fact that does not resolve a real mission still refuses (no silent fallback to the repository root); the refusal path is exercised by a test. | Security | High | Open |
| NFR-002 | Additive, layer-clean thread-through | New `owned` carriers are additive keyword args defaulting `None`; no existing signature breaks, and the import direction `specify_cli → coordination → mission_runtime` is preserved (no new reverse edge). | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Mirror the #6023 carrier pattern | Reuse `_owned_checkout.OwnedCheckoutOption` / `resolve_owned_or_refuse` and `LIFECYCLE_OWNED_TOPOLOGIES`; introduce no new owned-resolution authority and no new placement seam. | Technical | High | Open |
| C-002 | No matrix-format or writer-semantics change | The issue-matrix on-disk format and the locked re-read/splice/write semantics are unchanged; only the resolved write/read directory gains owned-awareness. | Technical | High | Open |
| C-003 | Red-first + p0-repro | A failing repro lands before the fix (red at merge-base), and a `p0_repro`-marked reproduction mirrors `test_p0_repro_6023_owned_acceptance_verdict.py`. | Technical | Medium | Open |

### Key Entities

- **OwnedCheckout**: the validated owned-checkout fact (`mission_slug`, owned root) threaded as `owned=`.
- **issue-matrix.json**: the per-mission record of criterion verdicts for cited GitHub issues; gates work-package approval.
- **Write-target gate**: `coordination.surface_resolver.resolve_for_write` → `mission_runtime.write_target_degrade.{resolve_write_target_or_degrade,_mission_meta_exists,assert_coord_write_materialized}`, the fail-closed authority that currently refuses an owned-only mission.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An owned-only mission's cited issue receives a recorded verdict through `issue-verdict --owned-checkout` (and via flagless adoption from inside the owned checkout), and its owning work package clears the issue-matrix approval gate — where both routes refuse fail-closed at the merge-base. — [build] · no-op passable: no
- **SC-002**: Zero behavior change for repository-root/coordination issue-verdict and for the three unrelated write-target-gate callers — demonstrated by the existing issue-matrix and gate regression suites staying green alongside the new owned positive cases. — [ratchet] · no-op passable: yes (paired with the SC-001 owned positive cases on shared fixtures)

## Dependencies & Assumptions

- Builds on the merged #6023 owned-acceptance-authority fix and reuses its owned R/P/S test fixtures.
- Refs #6320 (this mission's issue; gating issue-matrix row), #6023, #5227, #5277 (context, non-gating).
- Assumes the downstream writer (`write_issue_matrix`) and placement authority (`resolve_placement_only`) already accept `owned` (confirmed during grounding).
