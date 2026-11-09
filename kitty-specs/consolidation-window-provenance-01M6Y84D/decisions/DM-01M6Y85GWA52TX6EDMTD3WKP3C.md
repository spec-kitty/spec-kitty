# Decision Moment `01M6Y85GWA52TX6EDMTD3WKP3C`

- **Mission:** `consolidation-window-provenance-01M6Y84D`
- **Origin flow:** `specify`
- **Slot key:** `specify.provenance.missing-window`
- **Input key:** `missing_window_rule`
- **Status:** `resolved`
- **Created:** `2026-11-08T18:54:08.778951+00:00`
- **Resolved:** `2026-11-08T18:55:06.361222+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How does the gate treat a WP with no recorded window (missions in flight before this ships, or a failed capture)?

## Options

- Fall back to the current approval-stamp bound, reported as a gap
- Refuse until the window is recorded
- Other

## Final answer

Fall back to the current approval-stamp bound for that WP and report the missing window as a gap in the output

## Rationale

_(none)_

## Change log

- `2026-11-08T18:54:08.778951+00:00` - opened
- `2026-11-08T18:55:06.361222+00:00` - resolved (final_answer="Fall back to the current approval-stamp bound for that WP and report the missing window as a gap in the output")
