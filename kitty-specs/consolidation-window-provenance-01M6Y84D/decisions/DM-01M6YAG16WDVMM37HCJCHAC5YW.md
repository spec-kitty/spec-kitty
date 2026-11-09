# Decision Moment `01M6YAG16WDVMM37HCJCHAC5YW`

- **Mission:** `consolidation-window-provenance-01M6Y84D`
- **Origin flow:** `plan`
- **Slot key:** `plan.window.opener`
- **Input key:** `window_opener`
- **Status:** `resolved`
- **Created:** `2026-11-08T19:34:50.332763+00:00`
- **Resolved:** `2026-11-08T19:37:05.043268+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Where does a WP window open?

## Options

- After the WP last returned to planned
- First claim, over-wide cases pinned as strict xfail
- Other

## Final answer

Window opens at the first claimed/in_progress move after the WP last returned to planned, skipping a leading branch-missing gap, ordered by lane topology with log-order fallback

## Rationale

_(none)_

## Change log

- `2026-11-08T19:34:50.332763+00:00` - opened
- `2026-11-08T19:37:05.043268+00:00` - resolved (final_answer="Window opens at the first claimed/in_progress move after the WP last returned to planned, skipping a leading branch-missing gap, ordered by lane topology with log-order fallback")
