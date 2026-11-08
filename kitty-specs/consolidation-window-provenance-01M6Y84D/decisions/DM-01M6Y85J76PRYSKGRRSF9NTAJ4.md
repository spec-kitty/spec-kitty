# Decision Moment `01M6Y85J76PRYSKGRRSF9NTAJ4`

- **Mission:** `consolidation-window-provenance-01M6Y84D`
- **Origin flow:** `specify`
- **Slot key:** `specify.provenance.writer`
- **Input key:** `window_writer`
- **Status:** `resolved`
- **Created:** `2026-11-08T18:54:10.150098+00:00`
- **Resolved:** `2026-11-08T18:55:07.788594+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Who writes the window SHAs while the Java write service is not yet pinned?

## Options

- Python status shells now; Java write service adopts the same key later via a spec-kitty-events issue
- Wait for the Java write service
- Other

## Final answer

The Python status shells write the namespaced key now; a spec-kitty-events issue asks the Java write service to adopt and type the same key

## Rationale

_(none)_

## Change log

- `2026-11-08T18:54:10.150098+00:00` - opened
- `2026-11-08T18:55:07.788594+00:00` - resolved (final_answer="The Python status shells write the namespaced key now; a spec-kitty-events issue asks the Java write service to adopt and type the same key")
