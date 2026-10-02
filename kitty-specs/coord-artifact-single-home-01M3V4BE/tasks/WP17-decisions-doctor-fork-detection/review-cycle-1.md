---
affected_files: []
cycle_number: 1
mission_slug: coord-artifact-single-home-01M3V4BE
reproduction_command:
reviewed_at: '2026-10-02T14:31:19Z'
reviewer_agent: cursor
wp_id: WP17
---

WP17 review cycle 1: changes requested.

Blocking:

1. `doctor decisions --repair` drops index entries whose events exist on either surface whenever the mission is not forked. `run_decisions_reconciliation` calls `_repair` for every unclean non-fork, and `_rebuild_index_from_log` keeps only ids present in the coordination `status.events.jsonl`. A prefix or single_home stream, including the empty placeholder used when the coordination worktree is unmaterialized, therefore wipes event-backed entries. The coordination-only ledger copy runs after that wipe and cannot restore them.

2. The NFR-002 zero-loss assertion across fixtures (a)-(d) is missing. `test_repair_never_drops_entries_on_forked_log` only locks fixture (a) at 0 index entries and does not check event-log bytes. Fixtures (b) and (c) have no repair monotonicity check.

3. The WP activity log is only the system prompt line. Record the red evidence, the commands and counts, and this cycle's decision.

Required: `--repair` must not remove an index entry that still has events on either surface. A genuine orphan (no events on either surface) may still be removed. Add a repair test over all four NFR-002 fixtures that asserts no index id and no event-log bytes are lost. Append the activity log through the CLI.
