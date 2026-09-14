---
affected_files: []
cycle_number: 1
mission_slug: post-merge-partition-integrity-01M2FQ80
reproduction_command: spec-kitty agent tasks move-task WP03 --to approved --mission post-merge-partition-integrity-01M2FQ80
reviewed_at: '2026-09-14T11:20:42Z'
reviewer_agent: user
wp_id: WP03
---

Approved by user: Review passed: genuine red-first #4090 disagreement, BOTH real readers driven. Retrospect leg = real _check_mission_completed -> _canonical_events_path -> resolve_status_surface (resolved the .worktrees/-coord husk = 11 open). Doctor leg = real _anchor_repair_root (re-anchors to primary root) + run_audit (scans repo_root/kitty-specs, mission found); structurally divergent (doctor path never imports resolve_status_surface). Raw --runxfail FAILS 11!=0; normal run 1 xfailed (XFAIL not XPASS). Load-bearing assert retrospect_open==doctor_open encodes FIXED expectation; HEAD-only surface facts are diagnostic-only, so WP04 flips green by removing the strict-xfail marker without editing the core assertion. Primary meta.json has NO merged_at; husk genuinely diverged (approved vs done, .worktrees path, non-ancestor). run_audit is integrity-only (no open-WP field), so reducing the doctor partition via the canonical status reducer is faithful. Scope = one new test file, no product changes. ruff check + format clean. Anti-pattern checklist: all PASS/N-A. Issue-matrix gate populated (all rows in-mission; #4090 attributed to WP03).
