---
affected_files: []
cycle_number: 1
mission_slug: approved-lane-resolution-route-01M7WW0Z
reproduction_command:
reviewed_at: '2026-11-20T19:35:15Z'
reviewer_agent: claude::reviewer-renata
wp_id: WP08
---

# WP08 review feedback (cycle 1). Reviewer claude::reviewer-renata (session_019C2Tk5ehA3TXonKhbxbaMR), verdict REJECT, commit f79deb79

Red-first matches (13 failed, 1 ratchet passed). These points are fine:
- the stamp SHA is used as the merge argument, with no TOCTOU;
- C-004 holds;
- `NO_APPROVAL_STAMP` and `STAMP_NOT_ON_LANE` behave correctly;
- the loosened first-parent check is safe;
- the conflict exit 3 is recoverable;
- `--force` is refused;
- static checks are clean;
- blast radius: 2259 passed.

## Must fix
1. (HIGH, CI-red) `test_no_dead_symbols` fails on `incorporate::{check_wp_may_incorporate, resolve_sibling_stamp}`. Make both private (rule 1).
2. (HIGH, CI-red) `test_no_legacy_terminology.py::test_lane_consolidation_phrasing_does_not_grow_beyond_baseline` fails. It is green on base 6ed0494ef. The comment at `incorporate.py:271`, "The lane-merge pipeline's single environment authority", must say "lane-consolidation pipeline".
3. (MED, integrity) Lane-committed merge attributes silently change the incorporate merge (`incorporate.py:311`). A plain-git `*.py merge=union` repro exits 0 with content neither side wrote, and remerge-diff lists nothing.
   - Fix by calling WP01's `assert_registered_merge_behaviour(repo, <paths changed among HEAD, the stamp and their merge-base>, attributes_source=<pre-run target tip>)` before the merge.
   - Refuse with a new code `INCORPORATE_MERGE_ATTRIBUTES_REFUSED` on `GitProbeError`, and add a real-git `merge=union` test.
   - RUNNER NOTE: WP01's code is not in lane-h's base. See the runner's message for how this item is sequenced.
4. (MED, likely diff-cover red) All behaviour tests run in a subprocess. In-process coverage of `incorporate.py` is 42%, and the new `workflow.py` lines are uncovered.
   - Add in-process real-git tests for `prepare_incorporation`, `incorporate_sibling`, `_newest_stamp` and `_require_idle_checkout`, plus a `CliRunner` test for the `--force` refusal.
   - Cover these branches: `CHECKOUT_BUSY` (`MERGE_HEAD` / dirty tracked file), the `PROBE_FAILED` paths (:194, 227, 229, 239, 251, 262, 291, 316, 321, 324-327), diverged stamps in `_newest_stamp` (:185), `already_present` (:310), the "stamp moved" print, and the conflict exit on the fix-prompt path.
5. (MED) Canceled content on the sibling lane: `_approved_stamps` (:163) skips canceled WPs but never checks that a canceled WP's commits are not under the chosen stamp.
   - Preferred: refuse early when a canceled WP of the sibling lane has commits reachable from the stamp.
   - Otherwise: a real-git test proving consolidate FAILs this exact shape.
6. (LOW) `incorporate.py:238` catches `except Exception`. Narrow it to the status read door's typed errors.
7. (LOW) The conflict next steps in `render_outcome` (:339-347) should offer `git merge --abort` (in the checkout) as the way to back out.
