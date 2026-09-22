---
affected_files:
- src/specify_cli/lanes/merge.py
- tests/merge/test_squash_target_newer_planning_3942.py
cycle_number: 1
mission_slug: squash-merge-target-safety-01M3551G
reproduction_command: pytest -q tests/merge/test_squash_target_newer_planning_3942.py
reviewed_at: '2026-09-22T19:08:00Z'
reviewer_agent: reviewer-renata
wp_id: WP01
---

# WP01 Review — Cycle 1

## Verdict

Changes requested. The ordinary-source fail-closed behavior, dry-run parity,
state preservation, custom-driver behavior, and target-newer planning control
are well covered and green. One historical planning-recency branch is not
preserved.

## Finding 1 — Source-newer overlapping planning edits become blockers

`_resolve_target_newer_planning_conflicts` resolves a conflicted PRIMARY
planning path only when `target_newer_primary_artifacts(target, source)` selects
the target. When both sides advanced the same planning path and the mission-side
commit is newer, the existing #3942 policy does not select the target; before
this change, `-X theirs` selected the mission side for the overlapping hunk.
After this change, the path remains unmerged and `_SquashMergeConflict` aborts.

This violates FR-006 / NI-006's requirement to retain the existing
history-aware planning policy. Reuse the same planning-recency authority in the
opposite direction for paths not already assigned to the target (with the target
still winning ties), then perform the same three-way merge with the selected
side preferred so disjoint edits survive. Do not broaden this exception to
ordinary source paths.

Add a regression in
`tests/merge/test_squash_target_newer_planning_3942.py` where both branches edit
the same planning hunk and the mission-side commit is demonstrably newer. Assert
successful squash integration and the mission value on target. Keep the
ordinary-source conflict pins green.

## Verified evidence

- Focused #4892 execution/forecast tests: green.
- Mutation restoring `-X theirs`: new ordinary-source guard fails as required.
- `tests/lanes tests/merge`: 1,223 passed, 1 skipped; only known linked-worktree
  charter-authoring failure #4873.
- Ruff and targeted mypy: green.
