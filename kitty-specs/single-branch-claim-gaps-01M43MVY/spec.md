# Mission Specification: single_branch claim gaps: stale occupant and claim base

**Mission Branch**: `issue-5680-single-branch-claim-gaps`
**Created**: 2026-10-04
**Status**: Draft
**Input**: Operator brief: deliver #5680 and #5663 so that single_branch work-package claims are neither blocked by finished missions nor missing their claim base.

Reader: a Spec Kitty maintainer reviewing the claim path of single_branch missions.

Code grounding: [`research/code-grounding.md`](research/code-grounding.md).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A finished mission no longer blocks a new claim (Priority: P1)

An operator starts a new single_branch mission on a topic branch and claims its first work package. The repository holds an older single_branch mission that was merged without `spec-kitty consolidate`. On the branch the operator is on, that mission's status still shows a work package `in_progress`. Today both claim verbs refuse with `WRITE_CHECKOUT_OCCUPIED`, naming the old mission (#5680), and the operator has no command to run that clears it.

**Why this priority**: it blocks every single_branch claim in this repository today, including dogfooded missions.

**Independent Test**: build two single_branch missions in one repository. Put the old one's work package `in_progress` on its own write branch, then carry that status onto a new branch. Claim on the new branch through each claim verb.

**Acceptance Scenarios**:

1. **Given** mission A (single_branch, write branch X) has WP01 `in_progress`, and the operator is on branch Y (cut from X) with mission B (single_branch, write branch Y), **When** the operator runs `spec-kitty implement WP01 --mission B`, **Then** the claim succeeds.
2. **Given** the same fixture, **When** the operator runs `spec-kitty agent action implement WP01 --mission B`, **Then** the claim succeeds.
3. **Control (same fixture shape):** **Given** mission A and mission B share write branch Y and A's WP01 is `in_progress`, **When** either claim verb runs for B, **Then** it refuses with `WRITE_CHECKOUT_OCCUPIED`.
4. **Control:** **Given** B's WP01 is already `in_progress`, **When** the operator re-runs the claim for B's WP01, **Then** the resume is allowed.

---

### User Story 2 - A live-occupant refusal tells the operator what to run (Priority: P2)

When the refusal is genuine (another WP is `in_progress` on the same write branch), the message names the occupying mission, its work package and the write branch. It also gives a command that the new mission's operator can run if the occupant is actually finished or abandoned.

**Why this priority**: an operator who hits the refusal should have a next step without reading code.

**Independent Test**: trigger the refusal and check that the message carries the mission, the work package, the branch and a runnable `spec-kitty agent tasks move-task` command. Run that command and retry the claim.

**Acceptance Scenarios**:

1. **Given** a live occupant on the same write branch, **When** a claim is refused, **Then** the message names the occupant's mission slug, its WP id and its write branch, and includes `spec-kitty agent tasks move-task <WP> --to blocked --mission <occupant> --note "<reason>"`.
2. **Given** the operator runs that command, **When** they retry the claim, **Then** it succeeds.

---

### User Story 3 - An agent claim records its claim base (#5663) (Priority: P3)

An agent claims a single_branch work package with `spec-kitty agent action implement`, commits, and moves it to `for_review` without `--force`.

**Why this priority**: #5659 already delivers this. This mission only verifies it and names the pin.

**Independent Test**: `tests/integration/test_single_branch_write_checkout_e2e.py::test_action_implement_records_claim_base_and_reaches_review`.

**Acceptance Scenarios**:

1. **Given** a single_branch mission, **When** `agent action implement WP01`, a commit, `mark-status` and `move-task WP01 --to for_review` run, **Then** `move-task` exits 0 and a claim-base ref exists.

### Edge Cases

- **The occupant's write branch is a protected-target mint** (`meta.json` `mission_branch`). The write branch is that minted branch, not `target_branch`.
- **The occupant's `meta.json` has no `target_branch`, or the write checkout is on a detached HEAD.** The write branch cannot be compared, so the occupant counts. This fails closed and keeps the old behaviour.
- **A finished mission whose write branch IS the current branch** (for example, merged by hand with `--commit-to-target` on the same branch). It still refuses. The new remedy (US2) is the way out.
- **Owned checkout (write checkout is not the repository root checkout).** Unchanged: the scan already returns nothing.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | Finished foreign-branch occupant does not block `implement` | As an operator, I want `spec-kitty implement` to ignore an `in_progress` WP whose mission's write branch is not the branch the write checkout is on, so that a mission merged elsewhere stops blocking my claim. | High | Open | [build] | no — paired with FR-003 on the same fixture |
| FR-002 | Same on `agent action implement` | As an agent, I want `spec-kitty agent action implement` to behave identically to `spec-kitty implement` for FR-001 and FR-003, so that both claim verbs agree. | High | Open | [build] | no — paired with FR-003 on the same fixture |
| FR-003 | Live same-branch occupant still refuses | As an operator, I want a claim refused with `WRITE_CHECKOUT_OCCUPIED` while another single_branch mission's WP is `in_progress` on the same write branch, so that sequential execution stays enforced. | High | Open | [build] | no — control for FR-001/FR-002 |
| FR-004 | Resume still allowed | As an operator, I want re-running the claim for the WP that is already `in_progress` to be allowed, so that resume keeps working. | High | Open | [build] | no — control |
| FR-005 | Runnable remedy in the refusal | As an operator, I want the occupied refusal to name the occupant's mission, WP and write branch, plus a `move-task … --to blocked` command I can run, so that I can clear a stale occupant without reading code. | Medium | Open | [build] | no |
| FR-006 | #5663 verified and pinned | As a maintainer, I want the agent-claim → commit → `for_review` sequence pinned by a named test, so that #5663 can close with evidence. | Medium | Open | [folded] | yes — already delivered by #5659; pinned by the existing e2e test |
| FR-007 | Docs and changelog | As a maintainer, I want the changelog and the `WRITE_CHECKOUT_OCCUPIED` descriptions (CLAUDE.md, `docs/context/topology.md`) to state the new scope, so that docs match the shipped behaviour. | Medium | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | No extra I/O per mission | The write-branch comparison adds no git subprocess per mission. It reads the `meta.json` already loaded by the scan and resolves the current branch once per scan. | Performance | Medium | Open |
| NFR-002 | Quality gates | Changed code passes `ruff check`, `ruff format --check --force-exclude` and `mypy`, and keeps cyclomatic complexity at 15 or below. | Maintainability | High | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | No weakening for live missions | Two live single_branch missions on the same write branch in one write checkout must still refuse. | Technical | High | Open |
| C-002 | No edits to foreign status | Never delete or rewrite another mission's status events. In particular, `reconcile-flake-family-01M34HR7`'s log stays untouched. | Technical | High | Open |
| C-003 | One authority | The write branch comes from `mission_runtime.single_branch_write_ref`. Topology comes from the stored-topology reader. Neither is re-derived from frontmatter or `lanes.json`. | Technical | High | Open |
| C-004 | No new gates | Add no new size, ratchet or allowlist gate. | Technical | Medium | Open |
| C-005 | Red-first | Each defect gets an issue-pinned reproduction that is red through a claim entry point before the fix (ADR 2026-07-17-1). After the fix it moves to its functional home and drops the `regression` marker. | Process | High | Open |

### Key Entities

- **Write checkout**: the one checkout a single_branch mission writes code and status into (`docs/context/topology.md`).
- **Write branch**: the branch a single_branch mission writes to. It is the protected-target mint (`meta.json` `mission_branch`) when one is recorded, otherwise `target_branch` (`mission_runtime.single_branch_write_ref`).
- **Occupant**: a repo-root-lane WP of another live single_branch mission that is `in_progress` on the write branch the checkout is on.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In this repository, the occupancy scan run from a checkout on a topic branch no longer reports `reconcile-flake-family-01M34HR7` WP04. — [build] · no-op passable: no
- **SC-002**: Both claim verbs pass on the stale-occupant fixture and refuse on the live-occupant fixture, in the same test file. — [build] · no-op passable: no
- **SC-003**: #5663 closes with a named pinning test. — [folded] · no-op passable: yes

## Assumptions

- A single_branch mission's status is authoritative only on its write branch. A copy carried onto another branch (by branching off or by integrating a merge) is a snapshot, not live state. This follows the CLAUDE.md status rule: "Status source of truth: the resolved status surface ... not the open worktree".
- Uncommitted work of an occupant on another branch is already covered: the dirty-checkout refusal and git itself block switching away from it.
