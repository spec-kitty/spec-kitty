# Decision Moment `01M6YAFYHT0RMVZB03THW1WWSE`

- **Mission:** `consolidation-window-provenance-01M6Y84D`
- **Origin flow:** `plan`
- **Slot key:** `plan.window.anchor-set`
- **Input key:** `lane_anchor_set`
- **Status:** `resolved`
- **Created:** `2026-11-08T19:34:47.611017+00:00`
- **Resolved:** `2026-11-08T19:37:01.945421+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Which approval stamps exempt a lane commit on the window path?

## Options

- Drop own-lane stamps, keep other lanes approved tips
- Windows only, no cross-lane exemption
- Other

## Final answer

Drop own-lane stamps (windows decide); keep other lanes' approved tips as exemption anchors (content inside another lane's reviewed tip); SC-001 reworded to state the exception

## Rationale

_(none)_

## Change log

- `2026-11-08T19:34:47.611017+00:00` - opened
- `2026-11-08T19:37:01.945421+00:00` - resolved (final_answer="Drop own-lane stamps (windows decide); keep other lanes' approved tips as exemption anchors (content inside another lane's reviewed tip); SC-001 reworded to state the exception")
