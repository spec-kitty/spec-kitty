# Implementation Plan: agent action implement refreshes a reused lane's workspace context

**Branch**: `issue-6650-agent-action-lane-context-refresh` | **Date**: 2026-10-30 | **Spec**: `kitty-specs/agent-action-lane-context-refresh-01M66FF3/spec.md`
**Input**: Mission specification from `kitty-specs/agent-action-lane-context-refresh-01M66FF3/spec.md`

## Summary

`spec-kitty agent action implement` is the third WP-claim path and the only
one PR #4584 left uncovered: when it claims a WP into an already-materialized
lane worktree, it runs `reenter_lane_self_heal`
(`src/specify_cli/cli/commands/agent/workflow.py:1729` →
`src/specify_cli/lanes/implement_support.py:603`) and never refreshes the
lane's persisted workspace context, so `current_wp` stays on the lane's first
WP and every later commit prints `ACTIVE_WP_CONTEXT_STALE` (#6650). The fix
routes the exists-path through the shared `refresh_reused_lane_context`
helper (`src/specify_cli/lanes/implement_support.py:330`) — the same helper
the native `implement` reuse arm and orchestrator-api `start-implementation`
already call — instead of adding a fourth variant of the refresh logic. A
red-first regression test beside
`tests/agent/test_orchestrator_lane_context_refresh.py` drives
`agent action implement` for a second WP into one lane and asserts the
refreshed context and the absence of the warning.

## Engineering Alignment

Single-seam bug fix; no schema, contract or API change. The invariant being
restored: **every claim path that reuses a lane worktree advances the lane's
persisted workspace context to the newly claimed WP** (PR #4584's acceptance,
"every claim path"). The fix is idempotent (the helper rewrites
`wp_id`/`current_wp`/`dependencies` when a context exists) and a no-op where
no lane context exists (repo-root/single-branch lanes, orchestrator-driven
missions, `lane_id=None`). The pinned invariant
`test_stale_exists_workspace_reenters_self_heal_not_create` (exists-path must
not route through `top_level_implement`) is untouched: the refresh call is
added beside `reenter_lane_self_heal` inside the exists-path closure, not in
place of it.

## Technical Context

**Language/Version**: Python 3.11+ (repo baseline)
**Primary Dependencies**: typer, rich (existing CLI surfaces only; no new dependencies)
**Storage**: N/A — one existing JSON file per lane workspace context
(`.kittify/workspaces/<mission>-<lane>.json`), rewritten by the existing
helper
**Testing**: pytest; targeted surfaces — the new regression test plus the
existing lanes/agent test files that cover the touched seam
(`tests/agent/test_orchestrator_lane_context_refresh.py`,
`tests/specify_cli/lanes/test_lane_context_refresh.py`,
`tests/specify_cli/cli/commands/agent/test_implement_single_resolution.py`,
`tests/lanes/test_planning_claim_self_heal.py`); no full-suite runs
(`NO_FULL_HEAVY_SUITES_IN_MISSION`)
**Target Platform**: Linux/macOS/Windows 10+ (CLI, pure Python change)
**Project Type**: single (CLI monorepo, `src/specify_cli/`)
**Performance Goals**: none beyond NFR-002 — the refresh is a file
read-modify-write with no git subprocess
**Constraints**: C-001 (no `top_level_implement` on the exists-path),
C-002 (idempotency and no-op shapes preserved), C-003 (terminology canon)
**Scale/Scope**: ~5 lines of production code in one function, one regression
test file, one changelog entry, one docstring update

## Charter Check

- **Single canonical authority** — pass: the fix adds a call to the ONE
  refresh helper; no new authority. NFR-001 pins the call-site count.
- **ATDD-first** — pass: the regression test is written first, witnessed RED
  on the base, then the fix lands (FR-002, SC-002).
- **Architectural alignment** — pass: no module-seam change; the call sits in
  the CLI layer (`workflow.py`) that already owns this seam, mirroring where
  `reenter_lane_self_heal` is invoked.
- **Terminology canon** — pass: Mission vocabulary only; no new CLI flags.
- **Change-scope reconciliation** — smallest-viable-diff picks one production
  function + one test file; Boy-Scout stays inside that file set (update the
  helper's docstring that currently says "both WP writers that reuse a lane");
  Locality blocks any wider cleanup.

## Project Structure

### Documentation (this mission)

```
kitty-specs/agent-action-lane-context-refresh-01M66FF3/
├── spec.md              # committed
├── plan.md              # this file
├── research.md          # grounding findings (discovery output)
└── tasks.md             # Phase 2 output (/spec-kitty.tasks)
```

### Source Code (repository root)

```
src/specify_cli/cli/commands/agent/workflow.py   # _reenter_self_heal closure: + refresh call
src/specify_cli/lanes/implement_support.py       # refresh_reused_lane_context docstring: "both" → "every"
tests/agent/test_agent_action_lane_context_refresh.py   # NEW regression test (red-first)
docs/changelog/CHANGELOG.md                      # [Unreleased] entry
```

**Structure Decision**: single-project layout; only existing surfaces are
touched, plus one new test file named after the contract it pins (following
the `test_orchestrator_lane_context_refresh.py` precedent beside which the
issue asks for it).

## Implementation Concern Map

### IC-01 — Exists-path context refresh on the third claim path

- **Purpose**: Make `agent action implement` advance a reused lane's persisted
  workspace context to the newly claimed WP through the shared helper, so
  later lane commits stop warning `ACTIVE_WP_CONTEXT_STALE`.
- **Relevant requirements**: FR-001, FR-002, NFR-001, NFR-002, C-001, C-002,
  C-003
- **Affected surfaces**: `src/specify_cli/cli/commands/agent/workflow.py`
  (`_reenter_self_heal`, ~line 1726), `tests/agent/` (new file),
  `src/specify_cli/lanes/implement_support.py` (docstring only),
  `docs/changelog/CHANGELOG.md`
- **Sequencing/depends-on**: none (single concern)
- **Risks**: calling the refresh with a mission handle that does not match the
  context filename (mitigated: `workflow.py` already passes the same resolved
  `mission_slug` to `top_level_implement`, which saves the context under that
  name); running the refresh on a single-branch/repo-root lane (safe: no lane
  context is persisted for those shapes, the helper no-ops on a missing
  context).

## Design Notes (Phase 1)

- **No `data-model.md`**: no entity, field or invariant changes — the
  `WorkspaceContext` shape is untouched; the fix changes when one existing
  helper is invoked.
- **No `contracts/`**: no interface is added or changed (the CLI surface is
  byte-identical; only stderr warning noise disappears). Recorded as
  `contracts: "none"` in `meta.json` with this rationale, per the plan
  contract.
- **No `quickstart.md`**: no user-facing workflow changes to document beyond
  the changelog entry and the touched docstring.
