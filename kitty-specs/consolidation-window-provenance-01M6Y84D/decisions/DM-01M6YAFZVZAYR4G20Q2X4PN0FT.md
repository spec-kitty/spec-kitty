# Decision Moment `01M6YAFZVZAYR4G20Q2X4PN0FT`

- **Mission:** `consolidation-window-provenance-01M6Y84D`
- **Origin flow:** `plan`
- **Slot key:** `plan.window.resume-anchors`
- **Input key:** `resume_anchor_scope`
- **Status:** `resolved`
- **Created:** `2026-11-08T19:34:48.959466+00:00`
- **Resolved:** `2026-11-08T19:37:03.498166+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

On resume, do frozen dependency-lane tips apply to both closed world and the approved bound?

## Options

- Both, flips named red-first
- Closed world only
- Other

## Final answer

On resume, one frozen claim-time anchor set feeds both closed world and the approved bound; each verdict flip named in NFR-002 with a red-first test through consolidate --resume

## Rationale

_(none)_

## Change log

- `2026-11-08T19:34:48.959466+00:00` - opened
- `2026-11-08T19:37:03.498166+00:00` - resolved (final_answer="On resume, one frozen claim-time anchor set feeds both closed world and the approved bound; each verdict flip named in NFR-002 with a red-first test through consolidate --resume")
