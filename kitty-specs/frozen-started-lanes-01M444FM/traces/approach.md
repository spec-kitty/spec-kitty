# Approach — frozen-started-lanes-01M444FM

- 2026-10-04 — Started from a five-lens read-only grounding squad (reproducer, root-cause, related issues, architect,
  test suite). The reproducer confirmed #5573 live on main through the CLI before any spec work.
- 2026-10-04 — Approach: a structural constraint, not a tie-break patch. Started work packages' recorded lanes become
  an input the pure lane computation honours. It refuses only the unsatisfiable cases, before the first write.
- 2026-10-04 — Post-specify squad (renata, priti) returned READY WITH FOLDS. It split "absent" from "unreadable"
  status, gave each refusal reason its own remedy, and widened the started definition to cover forced and
  blocked→in_progress moves.
- 2026-10-04 — Post-tasks squad returned 5 HIGH findings, all applied. Two were gates the plan had wrong: the dead-symbol gate name, and C901 baselined off for `compute.py`. Lesson: verify each named gate file can actually fail before citing it.
- 2026-10-04 — WP01 found that the existing #3311 / provenance-guard tests' "amendment" was a silent no-op: a text
  `str.replace` that never matched once finalize had rewritten the YAML. That is a second reason those tests missed
  #5573. They now amend through the frontmatter API and raise if nothing changes.
- 2026-10-04 — NFR-001 spot check (WP03 implementer): a 30-WP re-finalize with 5 started WPs, median of 5 runs over two rounds, took 0.962 s / 0.988 s before and 0.968 s / 0.987 s after. No measurable overhead.
- 2026-10-04 — Live evidence on lane-d (all WPs merged), using the #5573 issue reproducer through the real CLI:
  - **Amend arm:** finalize-tasks exits 0; `lanes.json` is lane-b = (WP02, WP01), with LANE_ID_CHANGED False. The
    production allocator returns the original lane-b worktree with WP02's commit visible. Before the fix, the same
    flow ended in `LaneWorkTipUnknownError`.
  - **Both-started arm:** exits 1 with LANE_MEMBERSHIP_FROZEN / started_lanes_collapsed; `lanes.json` and HEAD are
    unchanged.
  - **`spec-kitty implement WP02`:** refused with "already claimed by 'qa'". That is the fixture's claimant identity,
    unrelated to lanes, so the allocator evidence stands (analysis finding C1).
