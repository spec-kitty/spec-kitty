# Decision Moment `01M774W50DJNYP39QVKD7MN7FH`

- **Mission:** `review-context-wp-diff-01M774QF`
- **Origin flow:** `specify`
- **Step id:** `diff_size_policy`
- **Input key:** `diff_size_policy`
- **Status:** `resolved`
- **Created:** `2026-11-12T05:49:45.869363+00:00`
- **Resolved:** `2026-11-12T06:03:48.390880+00:00`
- **Resolved by:** `operator`
- **Opened by:** `claude`
- **Other answer:** `true`

## Question

Q1: How is the inlined WP diff bounded in the review prompt?

## Options

- A (rec): always inline stat + commit list; inline full patch up to a cap (~400 changed lines / 32 KB), else truncate per file with a marker and print the exact git diff command for the remainder
- B: never inline patch text; stat + commit list + one exact command only
- C: write the full diff to a file beside the review prompt and reference it

## Final answer

Commands only: no inlined patch and no diff file. The prompt carries the WP range base..tip with provenance, the implementation commit list, a compact stat, and the exact git log / git diff commands scoped to owned paths. #7578 Done-when reinterpreted: non-empty, window-limited range + commits + stat with matching commands.

## Rationale

Operator ruling 2026-11-12: the reviewer can fetch the diff with git tooling; the benchmark failure was an empty/unbounded command, not a missing inline diff.

## Change log

- `2026-11-12T05:49:45.869363+00:00` - opened
- `2026-11-12T06:03:48.390880+00:00` - resolved (final_answer="Commands only: no inlined patch and no diff file. The prompt carries the WP range base..tip with provenance, the implementation commit list, a compact stat, and the exact git log / git diff commands scoped to owned paths. #7578 Done-when reinterpreted: non-empty, window-limited range + commits + stat with matching commands.")
