# Approach

- **[2026-11-11][plan] Cut over through the shared build.** `docs-pages.yml` calls `docs-site-build.yml`, a `needs: deploy` smoketest reuses the canary's live-site probe, the canary is retired into it and `docs/llms.txt` is deleted. Tests first, through the job-graph model that evaluates the real `if:` conditions (#7484).
- **[2026-11-11][close] Assess.** The plan held: two work packages, red-first job-graph tests, the canary retired into the smoketest. The one detour was a post-approval fix commit that consolidate refused (LANE_MOVED_AFTER_APPROVAL); a re-review cleared it. Lesson: fold review findings before approval, or accept that a fix after approval means another review.
