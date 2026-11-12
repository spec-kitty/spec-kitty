# Decision Moment `01M774W8SW9GE4VN8QAR59MJ9S`

- **Mission:** `review-context-wp-diff-01M774QF`
- **Origin flow:** `specify`
- **Step id:** `commit_to_target_anchor`
- **Input key:** `commit_to_target_anchor`
- **Status:** `resolved`
- **Created:** `2026-11-12T05:49:49.756987+00:00`
- **Resolved:** `2026-11-12T06:03:50.198873+00:00`
- **Resolved by:** `operator`
- **Opened by:** `claude`
- **Other answer:** `true`

## Question

Q3: On commit-to-target single_branch (no wp_window / lane_head recorded), how is the range anchored?

## Options

- A (rec): read-side only: base = commit that introduced the FR-021 opener event (fallback wp-base ref), tip = commit that introduced the for_review event; no writer change
- B: add a new stamp on the write checkout HEAD at claim/for_review (writer change touching ADR 2026-11-08-2 W-1)

## Final answer

Widen the Mission: add the writer stamp (wp_window open_sha and lane_head) for commit-to-target single_branch at the write checkout HEAD, and accept the resulting consolidation-verdict change (check_write_branch_windows reads recorded windows). Requires an amendment to ADR 2026-11-08-2.

## Rationale

Operator ruling 2026-11-12: one canonical window authority on every topology instead of a read-side derivation. Foreign-commit treatment on a shared target is a plan-phase design point to escalate if it changes refusal codes.

## Change log

- `2026-11-12T05:49:49.756987+00:00` - opened
- `2026-11-12T06:03:50.198873+00:00` - resolved (final_answer="Widen the Mission: add the writer stamp (wp_window open_sha and lane_head) for commit-to-target single_branch at the write checkout HEAD, and accept the resulting consolidation-verdict change (check_write_branch_windows reads recorded windows). Requires an amendment to ADR 2026-11-08-2.")
