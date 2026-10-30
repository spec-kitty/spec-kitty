---
affected_files: []
cycle_number: 6
mission_slug: reconcile-run-scope-01M66YH3
reproduction_command:
reviewed_at: '2026-10-30T19:04:44Z'
reviewer_agent: reviewer-renata
wp_id: WP02
---

REJECT (review round 1, reviewer-renata)

Blocker (docs/changelog/CHANGELOG.md:212): the `### Internal` section forbids a `**Before:**` / `**After:**`
contrast (scripts/docs/check_changelog_style.py `check_internal_shape`, FR-009(c)). The gate runs un-guarded
in the always-on docs-lint CI job and exits 1 on this entry (0 errors on HEAD~1, 1 at HEAD).

Minimal fix: fold the bullet into one flowing line with no Before/After labels, and take the two nits while
rewriting: say the `applies` rule is "unchanged in both scopes" (a `regenerated_urns=None` call is
owner-agnostic by design) and name the dead edge as `PROJECT_* --requires--> mission_type:*` so "wherever it
sits" cannot read wider than the code. The reviewer verified its suggested rewrite: 0 errors, 685 characters.

Everything else passed: accuracy (no user-visible behaviour change; FULL/TOPIC_SCOPED/applies all described
correctly; merge_project_overlay still takes topic_scoped), placement (### Internal), single-file diff, no
shipped docs page describes the removed parameter, no forbidden terminology.
