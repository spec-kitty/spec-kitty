# Decision Moment `01M5ZBERXGAS37DZCNTPG1WMC0`

- **Mission:** `synthesis-record-integrity-01M5ZBC9`
- **Origin flow:** `specify`
- **Slot key:** `specify.locking.contention`
- **Input key:** `synthesis_lock_contention`
- **Status:** `resolved`
- **Created:** `2026-10-27T18:55:10.256157+00:00`
- **Resolved:** `2026-10-27T18:55:13.784911+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

What does a second synthesis run do when the lock is held?

## Options

- Short wait, then refuse
- Refuse immediately
- Wait indefinitely
- Other

## Final answer

Short wait (~10s), then refuse with CHARTER_SYNTHESIS_LOCK_HELD; nothing written

## Rationale

_(none)_

## Change log

- `2026-10-27T18:55:10.256157+00:00` — opened
- `2026-10-27T18:55:13.784911+00:00` — resolved (final_answer="Short wait (~10s), then refuse with CHARTER_SYNTHESIS_LOCK_HELD; nothing written")
