---
affected_files: []
cycle_number: 3
mission_slug: single-branch-topology-honesty-01M3M22V
reproduction_command:
reviewed_at: '2026-09-29T05:42:43Z'
reviewer_agent: claude
wp_id: WP07
---

# WP07 review feedback, cycle 3 (reviewer-renata)

**Verdict: changes requested, for one narrow item.** Every call site is now tested, and M6, M7 and M8 are caught. However, the safety branches of the new `record_tip_for_wp` have no test.

## Blocking

**Issue 1: `lane_tip.record_tip_for_wp`'s planning-lane skip and its never-raise guarantee are untested.**

- **Mutation M9.** In one throwaway copy I made two changes together:
  - replaced `except Exception: return` with `except ZeroDivisionError: return`;
  - removed `or is_planning_lane(lane)` from the skip.

  `test_issue_5115_record_points.py` and `test_lane_tip.py` stayed green: 19 passed.
- **Why this matters.** Without that skip, a **planning_artifact WP** reaching for_review through `agent status emit` or the orchestrator `transition` would call `code_lane_branch_name(..., "lane-planning")`, which raises `ValueError`. Without the swallow, that exception propagates **after** the status event has already landed. The command would report failure for a transition that actually succeeded. That is exactly the contract the docstring promises cannot happen.
- **Required fix.** Add focused tests that go red under M9. Either:
  - a unit test calling `record_tip_for_wp` for a WP in the `lane-planning` lane (returns `None`, writes no ref, does not raise); or
  - an `agent status emit --to for_review --force` of a planning WP that exits 0.

  Also add a no-raise case for a missing or corrupt `lanes.json`, and for a WP not in any lane.

## Call-site table (complete)

| Call site | Coverage |
|---|---|
| allocator REUSE `:1066` | tested |
| allocator CRASH_RECOVERY `:1131` | tested (M6 red: `test_crash_recovery_records_tip_despite_foreign_hook`) |
| allocator FRESH `:1254` | tested |
| `auto_rebase:926` | tested |
| `implement_support:544` | tested |
| `tasks_move_task:959` | tested |
| `agent/status.py:438` | tested (M7 red: `test_status_emit_for_review_records_tip_despite_foreign_hook`) |
| `orchestrator_api/commands.py:1940` | tested (M8 red: `test_orchestrator_transition_for_review_records_tip_despite_foreign_hook`) |
| `lane_tip.py:126` (inside `record_tip_for_wp`) | exercised by M7/M8, but its skip and swallow branches are untested (Issue 1) |
| merge helpers | covered by the allocator-route calls that run right after them |

## Verified

- `record_tip_for_wp` delegates to `record_tip(sha=None)`, which records the branch's **current** HEAD only.
- `record_tip` uses `check=False` and returns `None` for a missing branch, so it does not raise.
- Latency is at most one `lanes.json` read plus two git calls, and only on the for_review transition.
- The 7 named files give 80 passed (`-m "not timing"`, empty `GIT_CONFIG_GLOBAL`).
- `test_no_dead_symbols`: 34 passed. `test_layer_rules`: 74 passed.
