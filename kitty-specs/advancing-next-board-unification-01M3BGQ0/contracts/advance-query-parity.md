# Contract: Advancing decision == Query decision (board-authority parity)

The behavioral contract this mission enforces. "Contract" here is the parity between the two `spec-kitty next` modes, not an HTTP/GraphQL API.

## Public seam

- **Advance**: `decide_next_via_runtime(agent, mission_slug, result="success", repo_root=…)` → `DecisionEnvelope` (`src/runtime/next/runtime_bridge.py`).
- **Query**: `query_current_state(agent, mission_slug, repo_root=…)` → `DecisionEnvelope` (read-only).

## Contract clauses

### CT-1 — Actionable-step agreement
For any mission state, the advancing decision's `(action, wp_id)` for the actionable step MUST equal the query decision's `(mission_state/preview_step, wp_id)` for the same repo, whenever the board has an actionable WP. (FR-002)

### CT-2 — Rejected-WP re-dispatch
When a WP was rejected to a pre-review lane (`planned`) while the run is issued on `review`, the advancing decision MUST be `kind=step action=implement wp_id=<that WP>`, exit 0 — on every topology (`single_branch`, `coord`, `lanes_with_coord`, `lanes`). (FR-001, US1/US3)

### CT-3 — Coord implement dispatch
On `coord`/`lanes_with_coord`, when a WP is ready in a pre-review lane on the coordination status surface, the advancing decision MUST be `kind=step action=implement wp_id=<WP>`, exit 0 — never `kind=blocked reason="No action mapped for WP step 'implement'"`. (FR-003, US2)

### CT-4 — Honest blocked floor
When the board has no actionable WP for the issued step, the advancing decision MUST be `kind=blocked` (exit 1) carrying a runnable named recovery command. It MUST NOT be exit-0 `kind=step`, and MUST NOT be a WP-less composed placeholder (`action=review, wp_id=null`). (FR-004, FR-005, US4)

**Recovery command per sentinel** (the assertion checks the string is a runnable `spec-kitty` invocation, not merely non-empty; reuse any existing blocked-recovery convention already in the codebase rather than inventing a parallel one):

| Sentinel | Recovery command |
|----------|------------------|
| `blocked:no_actionable_wp` (incl. dependency-walled) | `spec-kitty agent tasks status --mission <slug>` (inspect claim/dependency state) |
| `blocked:review_in_progress` (all `in_review`) | `spec-kitty agent tasks status --mission <slug>` (identify the holding reviewer) |
| unmaterialized coordination surface (CT-5) | `spec-kitty doctor workspaces --fix` (materialize the coord worktree) |

### CT-5 — Coord-read fail-closed
When the coordination surface is unmaterialized/deleted, the advancing coord-aware read MUST raise the typed fail-closed error (ADR 2026-09-24-2), surfaced as a blocked reason naming the unmaterialized surface — NOT collapsed into the generic `no_actionable_wp` floor. (NFR-003, US4 S4)

### CT-6 — No engine-state write
Evaluating the advancing decision in the re-dispatch case MUST leave the persisted run/engine snapshot (including `issued_step_id`) byte-identical. (NFR-001)

### CT-7 — Single authority
Both advancing WP-iteration builders (`_build_wp_iteration_decision`, `_map_wp_step_decision`) and the DAG-advance path MUST derive the step/WP from the same board authority query mode consults; no advancing path may emit a step/WP the board authority did not produce. (NFR-002)

## Test mapping

| Clause | Test (home) |
|--------|-------------|
| CT-1, CT-2 | `tests/runtime/test_bridge_parity.py` — reject → advance==query, absolute anchor `implement/WP01`, per topology |
| CT-3 | `tests/runtime/test_bridge_parity.py` — coord/lanes_with_coord implement dispatch, absolute anchor |
| CT-4 | `tests/runtime/test_bridge_parity.py` — review-none / all-in_review / dependency-walled → blocked+recovery |
| CT-5 | `tests/runtime/test_bridge_parity.py` — unmaterialized coord → typed error, not generic floor |
| CT-6 | `tests/runtime/test_bridge_parity.py` — snapshot byte-identical before/after |
| CT-7 | `tests/next/test_finalized_task_routing.py` + review against the parallel-authority inventory (research.md) |
