# Mission Specification: agent action implement refreshes a reused lane's workspace context

**Mission Branch**: `issue-6650-agent-action-lane-context-refresh`
**Created**: 2026-10-30
**Status**: Draft
**Input**: Issue #6650 — "`agent action implement` leaves lane context on the first WP".

## Mission Boundary

#3946 reported that reusing a lane for a new WP leaves the lane's persisted
workspace context's `current_wp` on the earlier WP, so every later lane commit
warns `ACTIVE_WP_CONTEXT_STALE`. PR #4584 (commit 48467e8fb9) fixed two of the
three claim paths by routing them through one shared helper,
`refresh_reused_lane_context` (`src/specify_cli/lanes/implement_support.py`):
the native `spec-kitty implement` flow (the `create_lane_workspace` reuse arm)
and orchestrator-api `start-implementation`. The third claim path —
`spec-kitty agent action implement` on an already-materialized lane worktree —
routes through `reenter_lane_self_heal` instead, which never refreshes the
context. This mission closes that gap by putting the exists-path onto the same
shared helper, not by adding a fourth variant of the refresh logic. Ownership
scoping is already correct (the guard scopes against the canonical active WP);
the defect is the stale-context warning and the stale `spec-kitty context info`
output, so scope changes are explicitly out of scope.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Second WP into a shared lane claims without stale-context noise (Priority: P1)

An implementing agent runs the prescribed
`spec-kitty agent action implement WP02 --mission <mission> --agent <agent>`
after WP01 in the same lane (per `lanes.json`) was implemented, reviewed and
approved. The command reuses the existing lane worktree (its only possible
path: the worktree exists). Today the lane's persisted workspace context keeps
`current_wp: WP01`, so every WP02 commit in the lane prints
`ACTIVE_WP_CONTEXT_STALE` on stderr and `spec-kitty context info` reports the
wrong WP. After this mission, the context advances to WP02 exactly as the
native `implement` path already does, and WP02's commits print no stale
warning.

**Why this priority**: This is the whole defect — the only user-visible
behaviour in the issue. Everything else in the mission exists to deliver this
story without regressing the paths already fixed.

**Independent Test**: Claim two WPs into one lane through
`agent action implement` in a coordination-topology git repo fixture and assert
the persisted context's `current_wp`/`wp_id`/`dependencies` follow the second
WP and the pre-commit guard's active-WP resolver emits no
`ACTIVE_WP_CONTEXT_STALE` warning.

**Acceptance Scenarios**:

1. **Given** a lanes mission whose lane hosts WP01 (approved) and WP02
   (planned) with a materialized lane worktree and a persisted lane context
   naming WP01, **When** `agent action implement WP02` runs, **Then** the
   persisted context reports `current_wp=WP02`, `wp_id=WP02` and WP02's
   declared dependencies, and `resolve_active_wp_for_branch` on the lane
   branch emits no `ACTIVE_WP_CONTEXT_STALE` warning.
2. **Given** the same setup re-run for the *same* WP (an idempotent retry of
   `agent action implement WP02`), **When** the command runs again, **Then**
   it succeeds and the context still names WP02 (the refresh is idempotent,
   no new merge commits appear from it).
3. **Given** a lane with no persisted context (an orchestrator-driven mission
   that never created one), **When** `agent action implement WP02` runs,
   **Then** no context is created (the helper's documented no-op shape is
   preserved).

### Edge Cases

- Same-WP retry: the refresh must be idempotent (`refresh_reused_lane_context`
  already is — it writes the same values).
- A planning lane or repository-root lane (`lane_id=None`, no lane worktree
  context): the helper is already a no-op there; the fix must not create a
  context for those shapes.
- A code lane whose `lane_wp_ids` no longer contains the claimed WP: the
  helper refreshes by lane identity, not membership, so no new failure mode.

## Requirements *(mandatory)*

### Functional Requirements

| ID | Title | User Story | Priority | Status | Delivery | No-op passable? |
|----|-------|------------|----------|--------|----------|-----------------|
| FR-001 | `agent action implement` refreshes a reused lane's workspace context | As an implementing agent claiming a second or later WP into a shared lane via `agent action implement`, I want the lane's persisted workspace context to follow the newly active WP so that later commits print no `ACTIVE_WP_CONTEXT_STALE` warning and `spec-kitty context info` reports the truth. | High | Open | [build] | no |
| FR-002 | Regression coverage through the third claim path | As a maintainer, I want a red-first regression test that claims two WPs into one lane through `agent action implement` and asserts the refreshed context and the absence of the stale warning, so the gap PR #4584 left cannot reopen silently. | High | Open | [build] | no |

### Non-Functional Requirements

| ID | Title | Requirement | Category | Priority | Status |
|----|-------|-------------|----------|--------|--------|
| NFR-001 | Single refresh authority | The exists-path refresh must route through the pre-existing shared `refresh_reused_lane_context` helper; no fourth copy of the refresh logic may be introduced (call-site count of the helper grows by exactly one, in the seam the third path already uses). | Maintainability | High | Open |
| NFR-002 | No new gate latency | The added refresh must add no git subprocess beyond what the helper already performs (it is a file read-modify-write); `agent action implement` wall-clock on the reuse path stays within noise of the pre-fix baseline. | Performance | Medium | Open |

### Constraints

| ID | Title | Constraint | Category | Priority | Status |
|----|-------|------------|----------|--------|--------|
| C-001 | Do not route the exists-path through `top_level_implement` | The pinned invariant `test_stale_exists_workspace_reenters_self_heal_not_create` (`tests/specify_cli/cli/commands/agent/test_implement_single_resolution.py:222`) must keep holding: `create_workspace` must not run when the workspace exists. | Technical | High | Open |
| C-002 | Idempotent and no-op shapes preserved | A same-WP retry stays idempotent; a lane with no persisted context stays context-free; `lane_id=None` stays a no-op. | Technical | High | Open |
| C-003 | Terminology canon | Mission (never Feature); no `--feature` aliases in new code or messages. | Business | High | Open |

### Key Entities

- **Lane workspace context** (`WorkspaceContext`): the persisted per-lane
  record (`.kittify/workspaces/<mission>-<lane>.json`) carrying `wp_id`,
  `current_wp`, `dependencies` and `lane_wp_ids`; the pre-commit guard reads
  it to resolve the active WP for a branch.
- **Claim path**: a CLI entry point that claims a WP into a lane. Three exist:
  `spec-kitty implement`, orchestrator-api `start-implementation`, and
  `agent action implement` (the exists-path of which runs
  `reenter_lane_self_heal`).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After `agent action implement` claims WP02 into a lane that
  already hosted approved WP01, the persisted lane context reports
  `current_wp=WP02` and `resolve_active_wp_for_branch` on the lane branch
  emits no `ACTIVE_WP_CONTEXT_STALE` warning — [build] · no-op passable: no
- **SC-002**: The regression test is RED on the mission's base commit and
  GREEN on the mission's final commit (ATDD-first, red witnessed before the
  fix) — [build] · no-op passable: no
- **SC-003**: The native `implement` and orchestrator-api
  `start-implementation` refresh behaviours and their existing tests are
  unchanged (no regression in the two already-fixed paths) — [build] ·
  no-op passable: no
