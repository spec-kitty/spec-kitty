---
affected_files: []
cycle_number: 2
mission_slug: consolidate-retarget-01M7M5JA
reproduction_command:
reviewed_at: '2026-11-17T12:48:04Z'
reviewer_agent: claude::orchestrator
wp_id: WP05
---

# WP05 rework (orchestrator, cycle 1): correct two statements against what the end-to-end tests proved

1. **Kill-window residual.** The ADR amendment and the how-to state that a kill between the retarget record commits and the `committed` persist resumes as `UNEXPLAINED_BRANCH_MOVE` (remedy `--abort --release-branch`). WP04's end-to-end test proves otherwise: a hard kill at `phase_advance._persist_retarget_committed` followed by `consolidate --resume` exits 0 and lands with exactly one record (the post-tip recorder and the idempotent, deduplicated record write cover it). Replace the residual with that observed behaviour, citing the test `tests/terminus/test_consolidate_retarget_resume.py`. Remove the `--release-branch` remedy for this case.
2. **Refusal list.** WP04's rework adds two up-front `RETARGET_RECORD_UNWRITABLE` causes:
   - the new target's `meta.json` carries the skip-worktree or assume-unchanged bit;
   - the new target does not carry the record, but the root checkout has untracked `kitty-specs/<slug>/` copies the landing would overwrite.

   Add both to the how-to's refusal table and to the ADR amendment's code list.
3. **"One retarget commit".** On a default-topology Mission the record commit is made on the topic branch and folded into the squash landing, so the new target shows no separate retarget commit; `retarget_history` holds exactly one entry. Say so where the docs describe what is recorded.

Run `check_changelog_style`, `check_spelling --pass unreleased` and `tests/architectural/test_no_legacy_terminology.py` again. Commit with a plain signed `git commit` of the three owned files only (spec-kitty commits are unsigned here; the branch must carry signed commits), then move WP05 to for_review.
