# Decision Moment `01M777A6718QF5QSVHNSVFK221`

- **Mission:** `review-context-wp-diff-01M774QF`
- **Origin flow:** `plan`
- **Step id:** `owned_review_refusal_trigger`
- **Input key:** `owned_review_refusal_trigger`
- **Status:** `resolved`
- **Created:** `2026-11-12T06:32:23.009105+00:00`
- **Resolved:** `2026-11-12T06:32:25.136135+00:00`
- **Resolved by:** `operator`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

Q7: When does OWNED_REVIEW_BASE_UNAVAILABLE fire once the review range resolves from the recorded window?

## Options

- Narrow: only when the scoped range is unavailable or no owned_files (code/message unchanged)
- Keep: whenever the claim commit cannot be found

## Final answer

Narrow: the refusal (code and message unchanged) fires only when the owned checkout's scoped range is unavailable or the WP declares no owned_files; cells pinned on an unresolvable claim commit are re-pinned to genuinely-unavailable fixtures, never deleted.

## Rationale

Operator ruling 2026-11-12: firing less often is the purpose of the friction reduction; reviews should only be blocked on actual lineage problems.

## Change log

- `2026-11-12T06:32:23.009105+00:00` - opened
- `2026-11-12T06:32:25.136135+00:00` - resolved (final_answer="Narrow: the refusal (code and message unchanged) fires only when the owned checkout's scoped range is unavailable or the WP declares no owned_files; cells pinned on an unresolvable claim commit are re-pinned to genuinely-unavailable fixtures, never deleted.")
