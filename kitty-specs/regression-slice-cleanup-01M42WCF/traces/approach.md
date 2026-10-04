# Approach — regression-slice-cleanup

Initial plan: one WP per issue (code domain), parallel lanes, implementer subagents per lane, a planted break in the lane worktree's `src/` before every removal, then marker edits. Priority: #5620 item 1 (scope-config reader guard).

## Close-out assessment (2026-10-04)

- **What changed from the plan.** Eight WPs grew to nine: WP08's sweep found 16 more chmod-unreadable tests failing as root, and WP09 fixed them all through a re-finalize.
- **Every lane ran a planted break before each removal.** Two independent reviews still rejected a WP each (WP02: the #5100 A3 rule; WP03: the `.bak` payload) because a removed e2e had been the last guard of an assertion no ledger row named. Lesson: a ledger's planted break proves only the axis it targets. A trim also needs a break for each other assertion the removed test made.
- **Wall-clock.** Parallel lanes with sonnet implementers and opus reviewers worked, but nine concurrent pytest runs made per-file timing noisy. Durations were recorded as call-time sums.
