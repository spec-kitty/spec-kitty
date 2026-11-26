---
affected_files: []
cycle_number: 1
mission_slug: approved-lane-resolution-route-01M7WW0Z
reproduction_command:
reviewed_at: '2026-11-20T19:19:31Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP10
---

# WP10 review feedback (cycle 1) — reviewer claude::reviewer-renata (session_019C2Tk5ehA3TXonKhbxbaMR), verdict REJECT, commits c2a4f799 + b2bd03a7

## Verified
- Red-first: 9 failed, 3 passed (the unchanged budget tests).
- Blast radius: 1108 passed, 8 skipped. Arch gates (no_dead_symbols, layer_rules, legacy terminology, status_read_single_door): 243 passed.
- ruff, format, mypy and C901 clean. The listing semantics are correct. No injection. C-001 holds. Octopus and hand-revert merges are shown on git 2.43.
- The budget bump from 12 to 13 is justified.

## Must fix
1. (MED) A failed merge listing leaves the reviewer with no route to the merges.
   - Location: `wp_range.py:538` and `context_block.py:16`. When `rev-list --merges` fails, the output is only a generic note. The fallback commands use pathspecs, and history simplification drops exactly the merges FR-007 exists to show.
   - Fix: when "merges" is in the listing gap, print one explicit line with full SHAs, e.g. `RESOLUTION MERGES: could not be listed; run git rev-list --merges <base>..<tip> and review each with git show --remerge-diff <sha>`.
   - Test: extend `test_merge_listing_failure_is_fail_soft` so it asserts that rendered line.
2. (LOW, fold) Add one ATDD test through a review entry point: `agent action review` (`workflow_executor.py:2267`) or the `next` review prompt (`runtime/next/prompt_builder.py:376`). Use the `_lane_with_merges` fixture and assert the `RESOLUTION MERGE (operator-authored, review these bytes): git show --remerge-diff <full-sha>` line for the hand merge.

## For WP13 (docs only)
`merge_own_changed_paths` treats octopus merges as unjudgeable, while the printed `--remerge-diff` command shows them on current git. The two can disagree by git version.
