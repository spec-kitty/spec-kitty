# Mission Specification: Advancing next: task-board authority unification

**Mission Branch**: `fix/advancing-next-board-unification`
**Created**: 2026-09-25
**Status**: Draft
**Input**: Unify advancing `spec-kitty next` step/WP-derivation with query mode's coord-aware finalized-task-board authority (folds #4980 + #4975).

## Overview

The documented autonomous control loop — `spec-kitty next --agent <a> --mission <m> --result success --json` — is a release blocker (both issues P0, milestone *MVP launch*) on two paths, which are two faces of **one** defect: the *advancing* loop derives the next step/WP from a different authority than *query* mode uses, and the two are allowed to disagree on the same canonical board state.

- **#4980 (review-branch face):** after the reviewer runs the REJECT command printed by `next`'s own review prompt, the rejected work package (WP) drops to lane `planned`. Every later advancing `next --result success` returns `kind=step action=review wp_id=null` with a "Run `spec-kitty next` to advance" composition placeholder, exit 0, **forever** — the rejected WP is never re-dispatched, while query mode says `implement / WP01`.
- **#4975 (implement-branch / coord face):** on the default `coord` (and `lanes_with_coord`) topology, the advancing loop reaches the implement step and returns `kind=blocked reason="No action mapped for WP step 'implement'"`, exit 1, on every call — while query mode and `orchestrator-api list-ready` both report `WP01` ready. The advancing path reads WP lanes off the primary planning dir with no coord-aware status surface, so it sees no lane rows.

A harness that trusts `next` therefore either spins on a success-shaped no-op (#4980) or wedges at exit 1 with a misleading reason (#4975), on the default topology and after any review rejection. This mission makes the advancing loop consult the **same** coord-aware finalized-task-board authority query mode already uses, so the two modes agree by construction — a single authority, not a branch-by-branch parity patch (the #4860 near-miss unified only the implement branch and only for the non-coord case, which is precisely why both issues remain).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Autonomous loop re-dispatches a rejected work package (Priority: P1)

An autonomous harness drives `spec-kitty next --result success`. The loop dispatches implement, the WP is handed off to `for_review`, the loop dispatches review, and the reviewer runs the printed REJECT command (`move-task WP01 --to planned --review-feedback-file …`). The harness calls `next --result success` again to continue.

**Why this priority**: This is the #4980 release blocker. Without it the documented autonomous loop is unusable after any review rejection at the final review round — it returns a success-shaped no-op indefinitely and neither re-dispatches the fix nor stops.

**Independent Test**: Drive a `single_branch` mission to a review rejection, then assert the next advancing `next --result success` re-dispatches `implement WP01` (agreeing with query mode) and never emits the WP-less `action=review, wp_id=null` composition placeholder as a live loop state.

**Acceptance Scenarios**:

1. **Given** an advancing run issued on the `review` step whose only WP was just rejected to lane `planned` (topology `single_branch`), **When** `next --agent <a> --mission <m> --result success --json` runs, **Then** it returns `kind=step action=implement wp_id=WP01`, exit 0.
2. **Given** the same rejected state, **When** query mode (`next --mission <m> --json`) is evaluated on the same repo, **Then** query mode itself returns the absolute value `mission_state=implement wp_id=WP01`, **and** advancing mode's `action`/`wp_id` equal query mode's (both the absolute anchor and the parity hold).
3. **Given** the re-dispatched implement is driven back to `for_review`, **When** advancing `next --result success` runs again, **Then** it re-dispatches `review WP01` (the loop closes correctly without any manual out-of-loop recovery).
4. **Given** the reviewer instead **approves** the WP, **When** the loop advances, **Then** it returns `kind=step action=accept` then `kind=terminal mission_state=done` (the approve control is unchanged, envelope pinned).
5. **Given** a **multi-WP** mission (WP01 with no deps, WP02 depending on WP01) where WP01 is rejected mid-mission back to `planned` while WP02 is dependency-gated, **When** advancing `next --result success` runs, **Then** it re-dispatches exactly `implement WP01`, WP02 remains not-claimable (dependency order undisturbed), and advancing mode agrees with query mode on both WPs' claimable status.

---

### User Story 2 - Autonomous loop dispatches implement on the default coord topology (Priority: P1)

An autonomous harness drives `spec-kitty next --result success` on a mission created with the default `coord` topology (or `lanes_with_coord`), reaching the implement step with a ready WP.

**Why this priority**: This is the #4975 release blocker. Without it the canonical autonomous loop cannot issue a single implement step on the **default** topology — it wedges at exit 1 with a misleading "No action mapped" reason while query mode says the WP is ready.

**Independent Test**: Drive a `coord` mission to a ready implement step and assert advancing `next --result success` dispatches `implement WP01` in dependency order, agreeing with query mode and `orchestrator-api list-ready`.

**Acceptance Scenarios**:

1. **Given** a `coord` mission whose first WP is ready (lane rows live on the coordination status surface), **When** advancing `next --result success` reaches the implement step, **Then** it returns `kind=step action=implement wp_id=WP01`, exit 0 — not `kind=blocked reason="No action mapped for WP step 'implement'"`.
2. **Given** the same coord mission, **When** query mode, advancing mode, and `orchestrator-api list-ready` are evaluated, **Then** all three return the absolute value `WP01` as the ready WP (absolute anchor, not only relative parity).
3. **Given** the identical fixture on `lanes_with_coord`, **When** advancing `next --result success` reaches the implement step, **Then** it returns `kind=step action=implement wp_id=WP01`, exit 0 (absolute anchor on the second coord-family topology, whose lane model differs from plain coord).
4. **Given** the identical fixture on `single_branch` and on `lanes`, **When** advancing `next --result success` runs, **Then** implement dispatch behaves as before (no regression on the topologies that already worked).

---

### User Story 3 - Combined face: review rejection on a coord topology (Priority: P1)

An autonomous harness drives `spec-kitty next --result success` on a **coord** (and `lanes_with_coord`) mission all the way to a review rejection — the intersection of the two folded faces (coord-aware status surface AND the review branch, simultaneously).

**Why this priority**: This is the load-bearing proof that the two faces are truly **unified**, not separately patched. A branch-by-branch fix can make single_branch review-parity green (US1) and coord implement-parity green (US2) while still diverging on coord review-reject — exactly the #4860 failure shape. This cell must be green for the mission to be complete.

**Independent Test**: Drive a `coord` mission to a review rejection (WP01 → `planned` via the coord status surface) and assert advancing `next --result success` re-dispatches `implement WP01` agreeing with query mode.

**Acceptance Scenarios**:

1. **Given** a `coord` mission with a run issued on the `review` step whose WP01 was just rejected to `planned` on the coordination status surface, **When** advancing `next --result success` runs, **Then** it returns `kind=step action=implement wp_id=WP01`, exit 0, equal to what query mode computes for the same repo.
2. **Given** the same on `lanes_with_coord`, **When** advancing `next --result success` runs, **Then** it likewise re-dispatches `implement WP01` (exit 0), agreeing with query mode.

---

### User Story 4 - Honest blocked signal when no work package is actionable (Priority: P2)

The autonomous loop advances into a state where the board genuinely has no actionable WP.

**Why this priority**: The unification must not convert a genuine dead-end into a different silent no-op. When there is truly nothing to dispatch, the loop must stop with an honest, actionable signal — the fallback floor the operator confirmed.

**Independent Test**: Construct a board with no actionable WP for the issued step and assert advancing `next --result success` returns `kind=blocked` with a named recovery command, not a WP-less composition placeholder and not exit-0 `kind=step`.

**Acceptance Scenarios**:

1. **Given** an advancing run on the `review` step where the board has no actionable WP (none `for_review`, none re-dispatchable), **When** `next --result success` runs, **Then** it returns `kind=blocked`, exit 1, whose `reason`/recovery payload names a concrete recovery command (a `spec-kitty` invocation the operator can run) — never the WP-less `action=review, wp_id=null` composition placeholder.
2. **Given** a board whose WPs are all `in_review` (claimed by other reviewers), **When** advancing `next --result success` runs, **Then** it returns `kind=blocked`, exit 1, whose reason names the in-review condition, not a generic no-op.
3. **Given** a **dependency-walled** board (the only remaining WP is dependency-gated by an un-approved dependency, so nothing is claimable), **When** advancing `next --result success` runs, **Then** it returns `kind=blocked`, exit 1, with a recovery command — never exit-0 `kind=step` and never the WP-less placeholder.
4. **Given** a `coord` mission whose coordination worktree is **unmaterialized** (declared but not checked out), **When** advancing `next --result success` performs the coord-aware status read, **Then** it surfaces the coord-read typed fail-closed error (per ADR 2026-09-24-2) — a blocked reason that names the *unmaterialized coordination surface* — and is explicitly NOT collapsed into the generic "no actionable WP" blocked floor (an empty primary substitution that fabricates "no WP" is forbidden).

---

### Edge Cases

- **Rejection before the loop picked up the review** (the "early" control, covered by an acceptance scenario below): the reviewer rejects while the run is still on `implement`. The loop must continue to re-dispatch `implement WP01` (unchanged behavior — this control already works and must not regress). *Given* a reject issued while the run is still on `implement`, *when* advancing `next --result success` runs, *then* it re-dispatches `implement WP01`, exit 0 (verifies FR-006's early-reject arm).
- **Approve control**: covered by US1 scenario 4.
- **Multi-WP non-final review round**: covered by US1 scenario 5 (the dependency-order-undisturbed property).
- **Forward-only DAG**: the run's issued step marker (`review`) is not rewound; the actionable *action within the step* is recomputed from the board each call. No persisted run/engine state is mutated (see NFR-001).

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status |
|----|-------|------------|----------|--------|
| FR-001 | Re-dispatch rejected WP on the review step | As an autonomous harness, I want advancing `next --result success` to re-dispatch `implement` for a WP that a rejection dropped to a pre-review lane — on every topology, and without disturbing the dependency order of sibling WPs — so the loop self-heals after a rejection instead of spinning on a placeholder. | High | Open |
| FR-002 | Advancing mode agrees with query mode | As an operator, I want advancing `next` and query `next` to compute the **same** actionable step/WP from the same canonical board, so the two modes never disagree on what to do next. | High | Open |
| FR-003 | Coord-aware status surface for advancing WP resolution | As an autonomous harness, I want advancing `next` to resolve WP lanes from the same coord-aware status surface query mode uses, so implement dispatch and review re-dispatch work on the default `coord` and `lanes_with_coord` topologies. | High | Open |
| FR-004 | Honest blocked floor with named recovery command | As an operator, I want advancing `next` to return `kind=blocked` (exit 1) with a concrete named recovery command (a runnable `spec-kitty` invocation) when the board has no actionable WP, so a genuine dead-end is an actionable stop, not a silent no-op. | High | Open |
| FR-005 | No WP-less composition placeholder as a live loop state | As an autonomous harness, I want advancing `next` to never emit the `action=review, wp_id=null` "Run spec-kitty next to advance" composition placeholder as an advancing result, so exit-0 `kind=step` always carries a real actionable step. Discharged by *action selection* (the decision layer never reaches the placeholder writer for a live advancing state), not by changing how the placeholder renders (the renderer defects #3909/#4988 are out of scope). | High | Open |
| FR-006 | Preserve approve / early-reject / other-topology behavior | As an operator, I want the approve control, the early-rejection control, and `single_branch` / `lanes` implement dispatch to be unchanged, so the fix adds no regression to the paths that already work. | High | Open |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|----------|--------|
| NFR-001 | Decision-layer-only, no engine-state write | The fix performs no persisted run/engine-state write and no DAG regression. **Verified by**: an assertion that the persisted run/engine snapshot (including the issued step id) is byte-identical before and after the re-dispatch call — not merely that the issued step id is unchanged. | Reliability | High | Open |
| NFR-002 | Single board authority at the shared action-selection seam | After the fix, one board→step/WP derivation authority is consulted by the advancing WP-iteration path, the DAG-advance path, and query mode; the pre-existing parallel authorities (see Key Entities → Parallel-authority inventory) each delegate to it or are retired. The single authority lives at the action-selection seam feeding both WP-iteration builders AND the DAG-advance path — NOT as per-branch dispatch inside `_state_to_action`. **Verified by**: review against the enumerated inventory + a test asserting no advancing path emits a step/WP the board authority did not produce. | Maintainability | High | Open |
| NFR-003 | Coord-read fail-closed consistency | The coord-aware status read used by advancing mode honors the coord-read fail-closed policy (ADR 2026-09-24-2): an unmaterialized/deleted coordination surface raises the typed error rather than substituting an empty primary read. **Verified by**: US4 scenario 4 (unmaterialized coord surfaces the typed error, not the generic blocked floor). | Reliability | High | Open |
| NFR-004 | No new whole-suite time cost | The regression coverage runs at the module blast-radius tier (`tests/runtime/`, `tests/next/`) in under ~90s locally; no new whole-repo suite is required to validate the change. | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|----------|--------|
| C-001 | Public-seam regression proof | The red-first regression must be observable through the public `decide_next_via_runtime` (advance) vs `query_current_state` (query) seam, not a private helper — the defect is only visible at the composed decision. Home: `tests/runtime/test_bridge_parity.py`. | Technical | High | Open |
| C-002 | ATDD red-first, issue-pinned | Each defect (#4980, #4975) lands an issue-pinned `@pytest.mark.regression` repro that is RED through the pre-existing entry point before the fix (ADR 2026-07-17-1). After the fix the transitional repro becomes a focused parity test or moves to a functional home; it is not left marked `regression`. | Technical | High | Open |
| C-003 | Terminology & canonical sources | Use canonical terms (Mission, WP, lane) and canonical CLI/test seams; do not mint a fifth lane reader or copy an older mission's structure. | Technical | Medium | Open |
| C-004 | Scope boundary | In scope: the advancing-vs-query step-derivation unification (#4980 review-regression + #4975 coord implement + their combined cell). Out of scope: the composition-placeholder renderer defects (#3909, #4988), the `--result failed/blocked` snapshot wedge (#4898), the move-task feedback-persistence edge (#4899), and the LWW reducer split-brain (#4990) — cross-linked, not folded. | Business | High | Open |

### Key Entities

- **Board authority**: the coord-aware, dependency-aware, lane-current derivation of "what step/WP is actionable now" from the finalized task board — the authority query mode consults today (`_finalized_task_board_override_step` mapping the board to a step, then `preview_claimable_wp(..., status_dir=<coord-aware>)` resolving the WP).
- **Advancing decision**: the `kind`/`action`/`wp_id`/`mission_state` envelope returned by `next --result success`; must be computed from the board authority.
- **Query decision**: the read-only envelope returned by `next --json` (no `--result`); already correct — the reference the advancing decision must match.
- **Issued step marker**: the run's persisted current step id (e.g. `review`); a forward-only loop marker that this fix does not rewind.
- **Parallel-authority inventory** (the 3–4 authorities that must collapse to one; exact file:line to be pinned in plan research): `_state_to_action` (`src/runtime/next/decision.py`), `_finalized_task_board_override_step` (`src/runtime/next/runtime_bridge.py`), `_should_advance_wp_step` + `_wp_blocks_step` (`src/runtime/next/runtime_bridge.py`), and `preview_claimable_wp` (`src/runtime/next/discovery.py`). NFR-002 is reviewed against this enumeration.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a `single_branch` mission, after a review rejection, advancing `next --result success` re-dispatches `implement WP01` on the first call (0 manual out-of-loop recovery steps required); the WP-less review placeholder never appears as a live loop state. (#4980)
- **SC-002**: On a `coord` mission, advancing `next --result success` dispatches `implement WP01` at the implement step (exit 0), instead of `blocked "No action mapped for WP step 'implement'"` (exit 1). (#4975)
- **SC-003**: The advance-vs-query parity matrix is green for **every** cell: {review-reject, implement-dispatch} × {`single_branch`, `coord`, `lanes_with_coord`, `lanes`} — including the combined review-reject × coord/lanes_with_coord cell (US3) — plus the approve and early controls; 0 query-vs-advance disagreements remain.
- **SC-004**: When the board has no actionable WP (review-step-none, all-in_review, dependency-walled), advancing `next --result success` returns `kind=blocked` (exit 1) with a runnable named recovery command in 100% of such cases (0 exit-0 `kind=step` no-ops, 0 WP-less composition placeholders).
- **SC-005**: The full #4980 reproduction script (`scripts/qa/` or the copy captured in this mission's tracer; the exact script from the issue's "Complete reproduction" block) prints `CONFIRMED: after a review-step rejection the loop spins on a WP-less placeholder review step (exit 0); controls behave` on the **pre-fix** tree, and on the **post-fix** tree its `bug` arm instead re-dispatches `implement WP01` (the script's CONFIRMED assertion no longer holds), with the `approve` and `early` control arms unchanged.
- **SC-006**: The #4975 coord-implement reproduction (advancing `next --result success` on a `coord` fixture) no longer returns `blocked "No action mapped for WP step 'implement'"` on the post-fix tree; it dispatches `implement WP01` (exit 0), matching query mode.

## Referenced Issues

- **#4980** (P0, MVP launch) — review-branch / step-regression face. Owned by this mission.
- **#4975** (P0, MVP launch) — implement-branch / coord-`status_dir` face. Owned by this mission.
- Cross-linked, NOT folded (see C-004): #3909 / #4988 (composition-placeholder renderer cluster), #4898 (`--result failed/blocked` snapshot wedge), #4899 (move-task feedback persistence), #4990 (LWW reducer split-brain), #4518 (derivation re-read perf — downstream beneficiary), #4860 (the near-miss that unified only the implement branch, without `status_dir`).

## Assumptions

- The `coord` topology is the default for a mission created on the primary branch; the autonomous loop is expected to work on it out of the box.
- Query mode's current board-derivation is the correct reference behavior (both issues and both grounding lenses treat it as the source of truth); US1 S2 and US2 S2 pin query mode's own absolute output so a co-regression in query mode cannot green-wash a relative parity assertion.
- The forward-only DAG has no legitimate `review → implement` engine regression; the loop marker stays put and the per-call action is recomputed (confirmed by the alignment lens).
