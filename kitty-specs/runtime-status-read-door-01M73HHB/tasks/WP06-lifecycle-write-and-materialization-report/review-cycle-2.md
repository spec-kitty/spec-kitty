---
affected_files: []
cycle_number: 2
mission_slug: runtime-status-read-door-01M73HHB
reproduction_command:
reviewed_at: '2026-11-11T08:19:49Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP06
---

# WP06 rework (orchestrator, after review cycle 1)

The cycle-1 review approved WP06, but two of its findings break this Mission's own success criteria. Fold them in before acceptance.

1. **SC-003 gap (blocking).** Two advancing runs return before the decision-log wrap:
   - a merged Mission whose coordination ref is retained but whose worktree was removed;
   - the completed-primary terminal.

   In both, `emit_mission_next_invoked`'s `write_dir` can now materialize or restore the coordination worktree without any report. SC-003 says every advancing run that materializes one reports it. Red-first: add a failing test for each path. Then report the materialization (the same `remediation` line and JSON), or, if materializing a worktree for a terminal or merged Mission is wrong, keep the lifecycle row from creating one, and say which you chose and why in add-history. No false report (FR-004).
2. **Orchestrator-api contract (blocking).** The answer verb returns `decision.to_dict()`, which can now carry `remediation`. The project rule in `src/specify_cli/orchestrator_api/envelope.py` is that an additive field is a minor bump. Bump `CONTRACT_VERSION` 1.26.0 -> 1.27.0 with a comment entry in the existing style, and update any test or doc that pins the version.
3. **Owned Mission report:** add a test of the report, or of its absence, for an owned coordination Mission, whichever matches today's FR-006 outcomes.
4. **Typing:** annotate `_print_remediation_line(decision)`.
