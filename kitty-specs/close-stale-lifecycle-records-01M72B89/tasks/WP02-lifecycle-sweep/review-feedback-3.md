# WP02 review feedback (cycle 3): changes requested

Reviewer: claude (reviewer-renata). Verdict: **reject**, one remaining closure-count hole. It comes from how a checkout decides *which* `started` record of a group is unpaired.

## Verified fixed

- B2: a record completed in a later checkout is no longer closed in an earlier one (`paired_somewhere`). The red-first test (`886d42d7` before `9e27c100`) is present and green, and the B1 tests and the twins test are still green.
- Docstring and trail-model bullet are accurate for the rule as written.
- Complexity, ruff, format and mypy are clean on `doctor/ops.py`. Targeted suite: 1069 passed, 5 skipped.

## Blocking

### B3 (medium): count-order labelling picks the wrong record, so a group is still over-completed after a merge (`src/specify_cli/doctor/ops.py`, `_unpaired_ids` / `_paired_counts`, via `unpaired_started`)

Pairing is count-based per `(mission_id, canonical_action_id)` group (C-004), and `unpaired_started` labels the **latest** `started` records unpaired. In a checkout where the completion actually belongs to the latest record, the label lands on the wrong record. The per-record-identity counts (`seen`, `paired_somewhere`) then compare different records across checkouts.

`implement::implement` for every work package of a Mission is one group, so this happens on any lanes Mission whose results are reported from different checkouts. Reproduced on `61921faf` with the WP's helpers in a temporary test file that I deleted:

1. In the root checkout, `started` for WP01 (50 h ago) and for WP02 (49 h ago), committed on the issue branch.
2. A linked worktree is created; WP01's completion is written and committed there.
3. WP02's completion is written and committed in the root checkout.
4. Sweep (threshold 24): `[('WP02', 'closed_abandoned', 'committed')]`. The root checkout reads S1, S2, C2 and labels S2 unpaired, so it abandons WP02, which it completed itself. `paired_somewhere` has S1 (paired by count in both checkouts) and nothing for S2.
5. After `git merge lane-topic`, the group is `WP01 started, WP01 completed, WP02 started, WP02 completed, WP02 abandoned`: three completions for two `started` records. That is the over-completion I1, B1 and B2 were about, and it masks the next orphan of `implement::implement` in this Mission. The JSON report also tells the operator that WP02 was the open one.

**Required change.** Decide which `started` records are unpaired by matching each completion to a `started` record of the same group with the same `agent` and `wp_id` first, falling back to read order for what is left. Do this locally to the sweep: `unpaired_started` and `doctor invocation-pairing` keep their count semantics, and C-004's group key does not change. With that labelling, the root checkout above sees S1 unpaired and S2 paired; `paired_somewhere[S1] == 1` (from the worktree) prevents the closure, and the existing tests keep their meaning.

An equivalent group-level rule is also acceptable. For each group, take the union across checkouts of `started` and completion records by identity (max multiplicity per checkout) and close no more than the union's deficit, choosing records the union leaves unpaired by the same agent/WP matching. Pick whichever is smaller and clearer. Keep complexity <= 15.

**Required test** (red before the fix): the scenario above. No `abandoned` record is written in either checkout, and after merging the lane into the issue branch `doctor_orphan_report(...)["orphan_count"] == 0` with exactly two completions in the group. Also add one same-checkout assertion: with S1, S2 and C2 in one checkout and both stale, the sweep's entry names WP01 (the record that is really open), not WP02.

## Non-blocking

- The labelling ambiguity also lives in WP01's `unpaired_started` (`doctor invocation-pairing` shows the latest record as the orphan). Fixing it there is out of scope for WP02, but a follow-up issue noting that count-order labelling names the wrong work package would be useful.
