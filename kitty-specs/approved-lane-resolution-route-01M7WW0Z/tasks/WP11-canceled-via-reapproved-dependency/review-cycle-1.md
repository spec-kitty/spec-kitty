---
affected_files: []
cycle_number: 1
mission_slug: approved-lane-resolution-route-01M7WW0Z
reproduction_command:
reviewed_at: '2026-11-20T19:36:06Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP11
---

# WP11 review feedback (cycle 1). Reviewer claude::reviewer-renata (session_019C2Tk5ehA3TXonKhbxbaMR), verdict REJECT, commit e52d6733

Red-first holds. Post-fix: `tests/consolidation` 3506 passed; `terminus -k canceled` 34 passed; arch gates 126 passed. The mutation tests are real. `_canceled_lane_anchors`, `_with_merged_in_canceled` and `_spine_content` are fine.

## Must fix
1. (HIGH) Approved dependency-lane work is reclassified as canceled. `_dependency_anchor_before_incorporating` (`reconciliation_canceled.py:367-386`) tests `canceled_tip ∩ commits_in_range(parents[0], sha)`. That range includes the merge itself and its whole second-parent side, and `canceled_tip` is C's full tip closure, which also holds the A commits C was cut from. So any merge on A's spine that C's tip reaches counts as "incorporating C", even a refresh or auto-rebase merge made before C was cut.
   - Real-git repro: A has `a1`, then a refresh merge `m0` of the Mission branch (bringing `s1`), then `a2`. C is cut from `a2` and commits `c1`. C is fully canceled, and A never merged C.
   - Result: C's own commits become `{s1, m0, a2, c1}` (the base gives `{c1}`), A becomes a carrier, approved WP01 work (`src/a.py`) is carried as canceled, and the run refuses with `CANCELED_REACHABLE_VIA_DEPENDENCY`. No attestation can lift that.
   - Fix: a merge M on A incorporates C only when some commit on M's non-first-parent side meets both conditions:
     - it is in `commits_in_range(M^1, p)` for a `p` in `parents[1:]`, with M itself excluded;
     - it lies on C's OWN first-parent spine (`first_parent_commits_in_range(coord_base_ref, C_tip)` minus what A's first-parent spine reaches before M).
     Never match against the full tip closure.
   - Tests: add the repro as a regression test (an ordinary merge on A before C is cut leaves C's own commits as `{c1}`, and A is not a carrier), in both the live and the frozen-tips variants. Add one end-to-end consolidate cell expecting the base verdict.
2. (LOW) Document two more residuals next to the fast-forward one, in the docstring, the history and the WP13 ADR list:
   - `git merge --squash` of C into A (C still owns `c1`, A is not a carrier);
   - a cherry-pick of `c1` onto A (patch-equivalent).
   Both need a re-approval that reviews the content.

Adversarial probes were correctly refused: an octopus merge of C plus another branch, and C merged through an intermediate branch.
