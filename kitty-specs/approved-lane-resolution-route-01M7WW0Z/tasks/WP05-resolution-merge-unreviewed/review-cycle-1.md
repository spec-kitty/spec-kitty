---
affected_files: []
cycle_number: 1
mission_slug: approved-lane-resolution-route-01M7WW0Z
reproduction_command:
reviewed_at: '2026-11-25T11:56:23Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP05
---

# WP05 review cycle 1 (lane-e 6d05e51fb5): REJECT (one MED)
Reviewer: claude::reviewer-renata (session_019C2Tk5ehA3TXonKhbxbaMR)

## Verified
- Red-first: 32 failed / 25 passed against the 93fa7b1c4e sources.
- Post-fix: 79 passed.
- Blast radius:
  - tests/consolidation: 3724 passed, 1 skipped, 10 xfailed
  - terminus subset: 70 passed
  - lanes: 36 passed
  - arch gates: 180 passed
  - ruff / C901 / format / mypy: clean
- Addenda 1-6 are met. The verdict never reads unreviewed_merges, and the memo stores successes only.
- The discriminator (exact-SHA record + FR-010 committed-tree rule) is correct, and every probe error fails closed.
- No duplicate authority and no private cross-module imports. The renames on WP01's files are pure.
- The cherry-picks are byte-identical to lane-h, and merge-tree against 93aa2771d0 is conflict-free.
- Real-git vectors all refuse or roll back as designed: hand merge, clone-local union, lane-committed union on a recorded merge, renormalize/filter, forged record, record naming another commit, dependency-lane hand merge, octopus, canceled window, and --dependency-ref at the hand-merge branch and at the external root. Unforced re-approval passes. A forged presync is not feasible.

## Must fix
1. (MED) A hand merge off the lane's first-parent spine bypasses the named refusal.
   - Where: reconciliation_bound._unreviewed_lane_merges -> approved_bound.first_parent_merges_beyond (`rev-list --first-parent --merges <tip> ^excluded`).
   - Repro (real git, end to end, `spec-kitty consolidate --yes`, squash and merge):
     1. After lane-a's approval, create X = commit-tree <tree with src/alpha/late.py> -p A -p <mission tip>.
     2. Create T = commit-tree <same tree> -p A -p X.
     3. Reset lane-a to T. Only T is on the first-parent spine, and its remerge-diff is empty, so X is never judged.
   - Result: the run exits 1 at the gate as unattributable, after branches moved and were rolled back, with a --dependency-ref hint. The named claim-time refusal (approach E) is defeated by one extra clean merge. WP04's unreviewed_merges lists only first-parent merges, so WP06's hint cannot name X either.
   - FIX:
     - Enumerate every merge in `tip ^coord_base ^claim_base` across all parents, not just first-parent merges.
     - Exclude merges on another Mission lane's own spine (that lane judges them), and merges the target or coordination history already holds.
     - Judge the rest with the same predicate: own stamps, then the auto-rebase record + FR-010, then own content.
     - Widen the WP04 advisory field the same way: a recorded-leeway edit to _collect_authored / _dropped_merges, or fill it from the new enumeration. WP06's hint then covers this shape too.
     - Add the repro as a test for both strategies: it must refuse RESOLUTION_MERGE_UNREVIEWED at claim time with no mutation (check reflog lengths and that no state.json is written).
     - Keep one rev-list per lane if possible (`rev-list --merges`, no --first-parent).

## Open question answered
Keep the canceled-window merge on RESOLUTION_MERGE_UNREVIEWED. It is the same fact, consumers route on the one code, and the text already says re-approval cannot lift it and gives the rebuild route. WP13 documents it as a named sub-case in the ADR amendment.

## Cheap add (re-probed in cycle 2)
A one-line test: resume with a hand merge added after the interrupt. The frozen lane tip plus lane_tips_moved_refusal should cover it.
