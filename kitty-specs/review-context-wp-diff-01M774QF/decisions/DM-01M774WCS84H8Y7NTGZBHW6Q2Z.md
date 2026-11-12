# Decision Moment `01M774WCS84H8Y7NTGZBHW6Q2Z`

- **Mission:** `review-context-wp-diff-01M774QF`
- **Origin flow:** `specify`
- **Step id:** `window_selector_home`
- **Input key:** `window_selector_home`
- **Status:** `resolved`
- **Created:** `2026-11-12T05:49:53.832729+00:00`
- **Resolved:** `2026-11-12T05:56:48.792455+00:00`
- **Resolved by:** `operator`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

Q5: Where does the FR-021 window-opener selector live so the review prompt (src/runtime, which may not import consolidation) can reuse it?

## Options

- A (rec): tidy-first move of the pure selector (window_opener_events, window_open_of, WindowOpen/WindowGap) to status/wp_window.py, re-exported from consolidation/wp_attribution; behaviour-preserving
- B: leave it in consolidation and add a second, review-side selector

## Final answer

A: tidy-first move of the pure FR-021 selector to status/wp_window.py, re-exported from consolidation/wp_attribution

## Rationale

Operator ruling 2026-11-12 (accepted recommendation); runtime may not import consolidation.

## Change log

- `2026-11-12T05:49:53.832729+00:00` - opened
- `2026-11-12T05:56:48.792455+00:00` - resolved (final_answer="A: tidy-first move of the pure FR-021 selector to status/wp_window.py, re-exported from consolidation/wp_attribution")
