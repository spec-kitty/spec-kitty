# Research findings — agent-action-lane-context-refresh-01M66FF3

## Grounding (2026-10-30, main @ 512567eee7)

**The issue still reproduces on current `main`; it was not superseded.**

- PR #4584 (`48467e8fb9`, merged 2026-09-16) introduced
  `refresh_reused_lane_context`
  (`src/specify_cli/lanes/implement_support.py:330`) and wired exactly two
  claim paths to it:
  1. the native `spec-kitty implement` flow — the `create_lane_workspace`
     reuse arm (`implement_support.py:506`);
  2. orchestrator-api `start-implementation`
     (`src/specify_cli/orchestrator_api/wp_lifecycle.py:579`).
- The third claim path — `spec-kitty agent action implement` over an
  already-materialized lane worktree — resolves the workspace once
  (`cli/commands/agent/workflow.py:1708`), then materializes through
  `_ensure_workspace_materialized(workspace, wp, _create_workspace,
  _reenter_self_heal)` (`workflow.py:1740`). On the exists-path this calls
  `reenter_lane_self_heal` (`lanes/implement_support.py:603`), which merges
  the recorded planning commit and dependency-lane tips and records the lane
  tip — and never touches the workspace context.
- `reenter_lane_self_heal` has exactly one production caller: the
  `agent action implement` exists-path (`workflow.py:1729`). Putting the
  refresh inside that seam covers the third entry point without a fourth
  variant of the logic, and without routing the exists-path back through
  `top_level_implement` (which `test_stale_exists_workspace_reenters_self_heal_not_create`
  at `tests/specify_cli/cli/commands/agent/test_implement_single_resolution.py:222`
  pins as forbidden).
- The stale warning is emitted by the pre-commit guard's active-WP resolver
  (`src/specify_cli/workspace/context.py:540-543`): `current_wp` from the
  persisted context vs the canonical active WP from the status event log.
  Scope is computed from the canonical active WP's `owned_files`
  (`context.py:559-570`), so the defect is noise plus a stale
  `spec-kitty context info`, not a wrong scope — matching the issue.

## Existing coverage to model on and not regress

- `tests/specify_cli/lanes/test_lane_context_refresh.py` — unit coverage of
  the shared helper + a git-backed pin of the native `implement` reuse path.
- `tests/agent/test_orchestrator_lane_context_refresh.py` — the
  orchestrator-api regression: drives the real CLI command against a real
  coordination-topology git repo, seeds WP01 approved with a materialized
  lane worktree + context, starts WP02 into the lane, asserts
  `current_wp == "WP02"` and no `ACTIVE_WP_CONTEXT_STALE` warning from
  `resolve_active_wp_for_branch`. The new test for `agent action implement`
  follows this shape (the issue asks for it next to this file).

## Decisions

- **Fix site**: call `refresh_reused_lane_context` from the
  `agent action implement` exists-path. Candidate placements: inside
  `_reenter_self_heal` in `workflow.py`, or at the end of
  `reenter_lane_self_heal` for code lanes. `reenter_lane_self_heal` does not
  currently receive the WP file path (needed for `parse_wp_dependencies`);
  the workflow.py call site already has `wp.path` in scope, so the refresh
  belongs beside the self-heal call in `workflow.py` unless review prefers
  threading the WP path into the seam. Decide at plan time; either way the
  shared helper stays the single refresh authority.
- **Mission placement note (tooling friction)**: the first scaffold
  (`agent-action-lane-context-refresh-01M66F6E`) was created from the
  repository root checkout while it sat on `main`, so its planning partition
  pointed at the protected branch and `spec-commit` refused
  (`PROTECTED_BRANCH_REFUSED`). That scaffold was abandoned before its spec
  was committed and removed; this mission was created with `--start-branch
  issue-6650-agent-action-lane-context-refresh --pr-bound`, matching the
  shape recent missions use (target = topic branch, PR carries it to `main`).

## Open questions

- None blocking. The issue body itself proposes this exact fix and its
  idempotency properties are already guaranteed by the helper (it rewrites
  `wp_id`/`current_wp`/`dependencies` unconditionally when a context exists,
  and is a no-op when the lane has none).
