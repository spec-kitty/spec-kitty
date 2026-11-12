# Decision Moment `01M774WARF9YWAD4MW4P35W8HC`

- **Mission:** `review-context-wp-diff-01M774QF`
- **Origin flow:** `specify`
- **Step id:** `lane_pathspec_scope`
- **Input key:** `lane_pathspec_scope`
- **Status:** `open`
- **Created:** `2026-11-12T05:49:51.759899+00:00`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

Q4: Scope the review diff to the WP owned_files on lane topologies too?

## Options

- A (rec): yes for the inlined patch and stat on every topology (lane-mates and parallel claims otherwise leak in), but list out-of-map paths touched in the window as a separate warning line so nothing is hidden
- B: owned_files scope on repo root only (current behaviour); lane diff unscoped

## Final answer

_(none)_

## Rationale

_(none)_

## Change log

- `2026-11-12T05:49:51.759899+00:00` - opened
