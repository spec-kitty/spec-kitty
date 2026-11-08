# Decision Moment `01M6Y84WAA6RZ8HEAFGAPC1H4R`

- **Mission:** `consolidation-window-provenance-01M6Y84D`
- **Origin flow:** `specify`
- **Slot key:** `specify.provenance.window-source`
- **Input key:** `window_source`
- **Status:** `resolved`
- **Created:** `2026-11-08T18:53:47.722962+00:00`
- **Resolved:** `2026-11-08T18:53:49.042166+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Where does the per-WP work window come from?

## Options

- Derive from existing lane_head stamps
- Record window SHAs on the transition event
- Other

## Final answer

Record window SHAs on the transition event (namespaced policy_metadata key; spec-kitty-events issue to type it); a failed capture is an explicit typed gap

## Rationale

_(none)_

## Change log

- `2026-11-08T18:53:47.722962+00:00` - opened
- `2026-11-08T18:53:49.042166+00:00` - resolved (final_answer="Record window SHAs on the transition event (namespaced policy_metadata key; spec-kitty-events issue to type it); a failed capture is an explicit typed gap")
