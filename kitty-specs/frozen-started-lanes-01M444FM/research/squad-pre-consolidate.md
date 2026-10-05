# Pre-consolidate squad: findings and dispositions

**Question:**
- Does the red reproduction now pass?
- Do the related-set decisions hold?
- Is there any collateral behaviour change?
- Can a started work package still move silently?

**Cast:**
- `debugger-debbie` (adversarial breaker): verdict **FOLD FIRST**;
- `architect-alphonso` (collateral, decisions and architecture fidelity): verdict **SAFE TO CONSOLIDATE**, with LOW
  folds.

Full reports are in the session scratchpad.

| # | Sev | Src | Finding | Disposition |
|---|---|---|---|---|
| 1 | HIGH | breaker | `lanes_with_coord` with an unmaterialized coordination worktree: the resolver returns a non-existent dir, which is read as "nothing started", so the WP moves silently when lane tips are absent (the #4959 defect class) | changed: WP03 reopened. Fail closed as `status_unreadable`, with the canonical materialize-first remedy, plus an e2e regression |
| 2 | LOW | collateral | `status_unreadable` hides the chained cause | accepted: folded into WP03 reopen |
| 3 | LOW | collateral | The preflight skips its dry run on empty lane inputs, so a removed started WP refuses only at the write (still restored by #5641) | accepted: folded into WP03 reopen |
| 4 | LOW | collateral | A bare `type: ignore` in `tests/lanes/test_frozen_lane_membership.py` | accepted: folded into WP03 reopen (out-of-map one-liner) |
| 5 | LOW | breaker | An absent status log with no lane tip lets a WP move | deferred_with_rationale: the spec explicitly defines "absent log → nothing history-started" (FR-007, US2 AS6, the legacy `tasks_finalize` ordering). Lane-branch commits-ahead as further evidence would be a scope extension; it is noted in the PR as a known limit. |
| 6 | INFO | breaker | A malformed log line is refused by the earlier frontmatter read without an `error_code` | accepted as designed: spec FR-007 and contract wording already updated (WP03 review) |
| 7 | INFO | breaker | A hand-edited frontmatter `lane: canceled` retires a started WP | out of scope: the existing #3713 projection, tracked by #5701 |
| 8 | INFO | both | No other writer rewrites an existing `lanes.json` around the frozen check; the doctor rebuild runs only without a manifest (#5703) | confirmed |
| 9 | INFO | collateral | Two "started" predicates remain | deferred: #5702 |

The breaker's ten attacks that **failed** (the fix held) are listed in its report, among them:
- `lanes_with_coord` with the coordination worktree present;
- a new overlapping WP;
- a greedy three-lane merge;
- a planning-lane neighbour;
- a renamed WP (refused);
- validate-only and real-run consistency;
- canceled-id reservation;
- reset-to-planned;
- tip-only evidence;
- cross-lane dependencies.
