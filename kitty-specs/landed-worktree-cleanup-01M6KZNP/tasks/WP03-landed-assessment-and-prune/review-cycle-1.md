---
affected_files: []
cycle_number: 1
mission_slug: landed-worktree-cleanup-01M6KZNP
reproduction_command:
reviewed_at: '2026-11-05T06:42:23Z'
reviewer_agent: claude
wp_id: WP03
---

# WP03 rework: operator ruling on unreadable processes (not a code review)

Decision Moment plan.prune.unreadable_process (2026-11-05), operator answer: **Skip and report**.

- A same-uid process whose `/proc/<pid>/cwd` cannot be read (PermissionError) no longer makes the probe unavailable. Skip it, and count it.
- `ProcessProbeResult` carries the count of uninspectable processes (e.g. `uninspected: int`), and the assessment/verdicts surface it so WP04 can print "N processes could not be inspected" (keep `to_json()` field names stable and add the count).
- `available=False` remains only for: no `/proc` (non-Linux) or `/proc` itself unreadable/unlistable.
- Document the residual in the module docstring next to the other-uid gap: a process whose cwd cannot be read (non-dumpable, other uid) is not detected.
- Tests: replace the "same-uid PermissionError → unavailable" expectation with "skipped and counted"; keep a test that a missing proc root is unavailable; add an assessment-level test showing a landed worktree stays LANDED when an unrelated unreadable process exists, and the count is reported.
