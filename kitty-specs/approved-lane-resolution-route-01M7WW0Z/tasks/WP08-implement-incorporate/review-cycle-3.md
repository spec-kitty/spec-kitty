---
affected_files: []
cycle_number: 3
mission_slug: approved-lane-resolution-route-01M7WW0Z
reproduction_command: spec-kitty agent tasks move-task WP08 --to approved --mission approved-lane-resolution-route-01M7WW0Z --agent claude::reviewer-renata
reviewed_at: '2026-11-25T10:59:27Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP08
---

Approved by claude::reviewer-renata: session:session_019C2Tk5ehA3TXonKhbxbaMR

# WP08 review cycle 3 (lane-h 93aa2771d0): APPROVE
Reviewer: claude::reviewer-renata (session_019C2Tk5ehA3TXonKhbxbaMR)

## Cycle-2 real-git probes re-run
- **Over-refusal shape:** now refuses with CONTESTED_COMMIT, names the shared commit, and gives the runnable attestation route, the consolidate-only note and the re-run line. It no longer calls w1 canceled content. This is ruling (A).
- **Evasion shape:** now refuses ("reaches merge ... whose own resolution changed src/canceled.py in the window of canceled WP02").

## Conditions
1. **Refusal text:** met.
2. **Only overridable reasons are lifted:** met. The check is gated on `outcome.reason in OVERRIDABLE_REASONS`, and the SPINE_UNREADABLE test is pinned.
3. **Public wp_windows / window_stamps:** met. The rename is pure, and the stamp annotation is a campsite fix.

## Re-runs
- incorporate, wp_attribution, family guard and canceled-attestation tests: 131 passed.
- no_dead_symbols: 37 passed.
- ruff, C901 and mypy: clean.

## Notes for WP13 (no change needed)
- **Parity with consolidate is "at least as strict", not exact.** The checks use attestation stamps as the only closed_world_anchors and planning_prefix=None for _is_bookkeeping. Both settings can only attribute more, so they fail toward refusal.
- **The window-merge probe** runs merge_own_changed_paths with no attribute source, so a committed union refuses (fail closed). WP07 composes the guard and the pinned env.
