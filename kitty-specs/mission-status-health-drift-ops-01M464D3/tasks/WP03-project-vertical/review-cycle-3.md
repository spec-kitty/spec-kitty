---
affected_files: []
cycle_number: 3
mission_slug: mission-status-health-drift-ops-01M464D3
reproduction_command:
reviewed_at: '2026-10-07T08:06:56Z'
reviewer_agent: user
wp_id: WP03
---

# WP03 rework: the Project read raises on a non-UTF-8 status.json (found at WP09, confirmed by its review)

`build_project` on a Mission whose `status.json` is not valid UTF-8 raises `UnicodeDecodeError` out of `_mission_activity` (through `materialize_snapshot`). FR-002/FR-003 require that the Project read never raises. Evidence: scratchpad `c12-wp09-review.md`, item 5.

Fix:
1. Catch it in `_mission_activity` with `except _UNREADABLE` (the existing tuple, or add `UnicodeDecodeError` to it if it is not there) and return None. The Mission still counts toward `missionCount`, but it adds no activity.
2. Red-first plant: an undecodable Mission beside a clean one, with its clean twin. It must fail on the unfixed builder. Add the matching mutation-table entry if the module keeps one.
3. Revert experiment on the fix.
Gates: the project module, the payloads and reality modules (`PYTHONPATH=<lane>/src`, run from a `git clone --shared` scratch clone of the primary checkout, because a lane worktree makes the corpus fall back), the ruff pair, and the battery fast leg (ruling 14).
