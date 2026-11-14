# Mission Specification: One checkout verdict for the planning commands

**Mission Branch**: `kitty/mission-checkout-verdict-agreement-01M7B1GG`
**Created**: 2026-11-13
**Status**: Draft
**Input**: #7594 (slice 1, delivered now) and #7633 (slice 2, waits for the operator ruling Q8)

Grounding: [`research.md`](research.md).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - The planning commands agree on the checkout (Priority: P1)

An operator creates a Mission without `--topology` from an existing topic branch. The CLI
mints a Mission topic branch and checks it out. The operator runs `setup-plan`, then the
tasks step runs `check-prerequisites`. Both report the same `branch_matches_target`
verdict for the same checkout, and both name the Mission topic branch as the expected
checkout and the original branch as the landing target. The tasks step no longer stops on
the branch the CLI chose.

**Why this priority**: today the supported create-to-tasks path stops (#7594, P1).

**Independent Test**: build a default Mission with the real create core, run both commands
from the repository root checkout before and after `finalize-tasks`, and from the
coordination worktree after settlement. Compare the branch contracts.

**Acceptance Scenarios**:

1. **Given** a default Mission before settlement, with the root checkout on the minted topic
   branch, **When** setup-plan and check-prerequisites run from the root checkout, **Then**
   both report `branch_matches_target: true`, `expected_checkout_branch` is the topic branch
   and `target_branch` is the landing branch.
2. **Given** the same Mission after `finalize-tasks` settled it to `lanes_with_coord`, with
   the root checkout back on the landing branch, **When** both commands run from the root
   checkout, **Then** both report `false` with the topic branch as the expected checkout;
   **When** they run from the coordination worktree, **Then** both report `true`.
3. **Given** an explicit-topology Mission on an unprotected target, **When** both commands
   run on the target, **Then** both report `true` with the target as the expected checkout
   (control: unchanged behaviour).

---

### User Story 2 - Status commits land where the read door reads (Priority: P2, slice 2)

A coordination-less Mission's status commit runs in the checkout the placement seam
names, so it lands where the status read door reads (#7633). **Deferred:** this waits for
the operator ruling Q8 on #7633 shape (b). No work package is generated for it in slice 1.

### Edge Cases

- Unreadable `meta.json` or an unresolvable Mission: the verdict degrades to a silent
  match (#3124), never a spurious disagreement.
- Invoked from a lane worktree on a divergent branch: `false` (FR-006 / #3124 preserved).
- Owned checkout: the expected checkout stays `owned.write_branch` (#5877 preserved).
- Protected explicit `single_branch` mint: the expected checkout is the minted branch
  (#5100 preserved).
- Landed default Mission: the seam names the target branch, so the verdict expects the
  target.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | One shared checkout verdict | As an operator, I want setup-plan and check-prerequisites to compute `branch_matches_target` and `expected_checkout_branch` through one shared helper, so that they cannot disagree for the same checkout. | High | Open | [build] | no — the settlement fixture is red on the pre-fix code in both phases |
| FR-002 | Expected checkout from the placement seam | As an operator, I want the expected checkout branch to be the placement seam's planning write ref, so that a default Mission's topic branch counts before and after settlement. | High | Open | [build] | no — paired with the explicit-topology control on the same fixture |
| FR-003 | Invoking checkout and landing target | As an operator, I want both commands to read the current branch from the invoking checkout and report `meta.target_branch` as `target_branch`, so that the landing target and the expected checkout are told apart. | High | Open | [build] | no — the coordination-worktree case is red on check-prerequisites before the fix |

### Deferred scope (slice 2, not declared here)

Slice 2 (#7633) routes the coordination-less status commit through the placement seam, so it
lands where the status read door reads. It waits for the operator ruling Q8 on #7633 shape
(b). Its requirement is added to this spec, with its work package, after that ruling; until
then no requirement ID is declared for it.

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No extra latency | Each command adds at most one seam resolution (no extra `git worktree list` beyond what the seam already does), and stays within the 2 s CLI budget on a typical project. | Performance | Medium | Open |
| NFR-002 | Gates stay green | No architectural allowlist grows; ruff, ruff format and mypy report zero issues on changed files. | Reliability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No second resolver | The verdict consumes `PlacementSeam.write_target`; it never re-derives placement from meta fields or topology itself (DIRECTIVE_044). | Technical | High | Open |
| C-002 | No seam change | Slice 1 changes no placement-seam behaviour, refusal code, exit code or commit destination. | Technical | High | Open |
| C-003 | Slice 2 waits for Q8 | No `coordination/transaction.py` change in slice 1. | Business | High | Open |

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For a default Mission, setup-plan and check-prerequisites report identical `current_branch`, `target_branch`, `expected_checkout_branch` and `branch_matches_target` in every acceptance scenario of User Story 1 — [build] · no-op passable: no
- **SC-002**: The existing owned-checkout, FR-006 lane-worktree and protected-mint pins stay green unchanged — [ratchet] · no-op passable: yes
