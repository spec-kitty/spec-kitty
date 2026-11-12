# Decision Moment `01M774W8SW9GE4VN8QAR59MJ9S`

- **Mission:** `review-context-wp-diff-01M774QF`
- **Origin flow:** `specify`
- **Step id:** `commit_to_target_anchor`
- **Input key:** `commit_to_target_anchor`
- **Status:** `open`
- **Created:** `2026-11-12T05:49:49.756987+00:00`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

Q3: On commit-to-target single_branch (no wp_window / lane_head recorded), how is the range anchored?

## Options

- A (rec): read-side only: base = commit that introduced the FR-021 opener event (fallback wp-base ref), tip = commit that introduced the for_review event; no writer change
- B: add a new stamp on the write checkout HEAD at claim/for_review (writer change touching ADR 2026-11-08-2 W-1)

## Final answer

_(none)_

## Rationale

_(none)_

## Change log

- `2026-11-12T05:49:49.756987+00:00` - opened
