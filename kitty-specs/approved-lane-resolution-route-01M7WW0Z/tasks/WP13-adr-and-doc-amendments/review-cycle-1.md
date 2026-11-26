---
affected_files: []
cycle_number: 1
mission_slug: approved-lane-resolution-route-01M7WW0Z
reproduction_command:
reviewed_at: '2026-11-26T06:43:12Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP13
---

# WP13 review cycle 1 (lane-m 5f2318bbd9): REJECT (1 CI-red, 4 LOW, 1 cross-WP)
Reviewer: claude::reviewer-renata (session_019C2Tk5ehA3TXonKhbxbaMR)

## Verified accurate against the merged code
- **A1:** RESOLUTION_MERGE_UNREVIEWED, including the recovery block, which matches _unreviewed_merge_block word for word.
- **A3:** rollback FR-009.
- **IncorporateCode:** the list of 10 values.
- **A2:** trust model, pins, .gitattributes fold, partial hint, #7497.
- **A4:** review-context lines.
- **AGENTS.md:** the replacements.
- **Format.**
- **Checks:** changelog style and spelling clean; tests/docs 2259 passed.

## Must fix
1. **(HIGH, CI-red)** test_no_legacy_terminology.py::test_lane_consolidation_phrasing_does_not_grow_beyond_baseline fails.
   - Offender: docs/changelog/unreleased/5604-approved-lane-resolution-route.fixed.md:6, "A canceled lane merged into a re-approved dependency lane…".
   - Fix: reword it (e.g. "brought into ... by a merge commit"), then re-run the gate.
2. **(LOW)** AGENTS.md:585 reads "an effective merge.renormalize is set". Change it to "is true".
3. **(LOW)** The ADR 2026-11-08-2 amendment (~:765) is missing WP12 item (d): when the merge listing failed on git < 2.36, the cannot-show form is printed.
4. **(LOW, deviation 1, accepted)** Cite test_one_side_merge_dropping_an_approved_edit_fails_approved_content_missing as "(on #7857)". The ADR-ordering conflict goes to the operator in the aggregate review.
5. **(LOW, deviation 3, recorded leeway)** docs/guides/how-to/recovery/troubleshoot-merge.md needs three additions:
   - the merge.renormalize refusal and its remedy;
   - the RESOLUTION_MERGE_UNREVIEWED re-review route;
   - the #7880 dependent-lane workaround.

## Cross-WP inconsistency (recorded leeway on WP09's two doc files)
- **The mismatch:** the WP09 docs row and the skill-reference row tell the operator to send back with `move-task <WP> --to planned --review-feedback-file <file>`. The refusal's own printed recovery (approved_bound.move_back_command, via _unreviewed_merge_block) prints `move-task <WP> --to in_progress`.
- **Fix:** the printed text is the single authority. Align both doc rows and troubleshoot-merge.md to it.
- **Test:** confirm that a test executes move_back_command's printed line for this refusal on a protected-coordination Mission (#7861 topology). If none exists, add one, with real git: claim refusal → run the printed move-back → exit 0, review cycle on the coordination branch, main untouched.
- **If `--to in_progress` fails there:** report to the reviewer before changing anything, because the fix would be a product change.
