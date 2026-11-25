---
affected_files: []
cycle_number: 2
mission_slug: remote-only-branch-remedy-01M7X5Z5
reproduction_command:
reviewed_at: '2026-11-20T21:33:12Z'
reviewer_agent: claude::python-pedro
wp_id: WP02
---

# WP02 reopened: dispatcher-requested fold (review MEDIUM)

For a MISSION_BRANCH_REF whose topic branch is gone both locally and on every remote, the refusal says
"exists only on a remote" and prints a fetch that cannot succeed. Fix: classify the topic-branch arm as
remote-only only when a remote-tracking ref proves a remote holds it; otherwise keep the plain
STATUS_SURFACE_REF_UNREADABLE. Red-first test for the gone-everywhere case.
