---
affected_files: []
cycle_number: 3
mission_slug: frozen-started-lanes-01M444FM
reproduction_command:
reviewed_at: '2026-10-04T23:34:36Z'
reviewer_agent: claude
wp_id: WP04
---

# WP04: pre-consolidate fold (docs only)

The WP03 pre-consolidate fold (commits `86910f75`, `06b9de10` on lane-c, now approved) changed the user-visible
`status_unreadable` refusal. The docs must mirror the shipped behaviour.

## [MEDIUM] Document the unmaterialized-coordination-worktree refusal and the appended cause

**New refusal case.** A previous `lanes.json` exists, but the resolved status directory is absent on disk. This is
the typical `lanes_with_coord` / `coord` mission whose coordination worktree is not materialized (fresh clone, CI,
removed worktree). Finalize now refuses with `LANE_MEMBERSHIP_FROZEN` / `status_unreadable` and the remedy:

> Materialize the coordination worktree, then re-run finalize-tasks. <canonical `CoordinationWorktreeUnmaterialized.next_step`>

That `next_step` names `spec-kitty doctor coordination --mission <slug> --fix`, with a manual `git worktree add`
fallback; a remote-only branch leads with `git fetch`. The reason for refusing: an absent coordination surface is never
read as "nothing started" (the #4959 fail-closed doctrine).

**Appended cause.** Every other `status_unreadable` remedy now ends with ` Cause: <cause message and next step>`.

**Pages to update** (reading the code in your lane after merging the latest lane-c, or by reading the lane-c branch
directly with `git show kitty/mission-frozen-started-lanes-01M444FM-lane-c:src/specify_cli/cli/commands/agent/mission_finalize_lanes.py`):
- `docs/api/finalize-tasks-internals.md`: the reason/remedy table and the evidence section (absent dir vs dir
  without a log).
- The ADR `docs/adr/4.x/2026-10-04-2-*.md`: the consequences/decision bullet on fail-closed status.
- `docs/architecture/execution-lanes.md`: only if it states the absent-log rule.

Afterwards, re-run `scripts/docs/docs_index.py --write` and confirm `check_docs_freshness.py --ci` reports errors=0.
