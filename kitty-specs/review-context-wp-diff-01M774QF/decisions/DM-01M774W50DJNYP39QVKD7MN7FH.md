# Decision Moment `01M774W50DJNYP39QVKD7MN7FH`

- **Mission:** `review-context-wp-diff-01M774QF`
- **Origin flow:** `specify`
- **Step id:** `diff_size_policy`
- **Input key:** `diff_size_policy`
- **Status:** `open`
- **Created:** `2026-11-12T05:49:45.869363+00:00`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

Q1: How is the inlined WP diff bounded in the review prompt?

## Options

- A (rec): always inline stat + commit list; inline full patch up to a cap (~400 changed lines / 32 KB), else truncate per file with a marker and print the exact git diff command for the remainder
- B: never inline patch text; stat + commit list + one exact command only
- C: write the full diff to a file beside the review prompt and reference it

## Final answer

_(none)_

## Rationale

_(none)_

## Change log

- `2026-11-12T05:49:45.869363+00:00` - opened
