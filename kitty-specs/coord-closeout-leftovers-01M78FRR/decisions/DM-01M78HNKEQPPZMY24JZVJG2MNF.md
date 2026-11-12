# Decision Moment `01M78HNKEQPPZMY24JZVJG2MNF`

- **Mission:** `coord-closeout-leftovers-01M78FRR`
- **Origin flow:** `plan`
- **Slot key:** `plan.reclaim.proof`
- **Input key:** `r1_reclaim_proof`
- **Status:** `resolved`
- **Created:** `2026-11-12T18:52:37.207173+00:00`
- **Resolved:** `2026-11-12T18:52:41.997403+00:00`
- **Resolved by:** `operator`
- **Opened by:** `claude`
- **Other answer:** `false`

## Question

#4041 R1: which proof must reclaim pass before deleting an archived Mission's coordination branch (is_absorbed refuses every squash-landed case)?

## Options

_(none)_

## Final answer

Recorded landing proof: require is_mission_merged (merged_at) AND the coordination tip at or behind the coordination tip the landing recorded; otherwise refuse RECLAIM_UNABSORBED. Legacy Missions without a recorded tip refuse.

## Rationale

Operator ruling 2026-11-12 after the WP04 R1 measurement (is_absorbed refuses: status.events.jsonl byte order differs, status.json add/add).

## Change log

- `2026-11-12T18:52:37.207173+00:00` - opened
- `2026-11-12T18:52:41.997403+00:00` - resolved (final_answer="Recorded landing proof: require is_mission_merged (merged_at) AND the coordination tip at or behind the coordination tip the landing recorded; otherwise refuse RECLAIM_UNABSORBED. Legacy Missions without a recorded tip refuse.")
