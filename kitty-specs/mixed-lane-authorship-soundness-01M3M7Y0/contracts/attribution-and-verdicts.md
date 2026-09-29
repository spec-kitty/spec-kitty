# Contract — WP commit attribution and mixed-lane verdicts

## C1 Stamp
- Every persisted transition of a WP mapped to a non-planning lane with an existing branch carries `policy_metadata.lane_head` = that branch's head SHA at persist time.
- Stamping never blocks or fails a transition (best-effort); absence is legal and is interpreted by C3.

## C2 Mixed lane
A lane from `lanes.json` with ≥1 WP in `approved`/`done` (Lamport snapshot) and ≥1 WP in `excluded_canceled_wp_ids` (the merge-side acceptable-cancel authority).

## C3 Verdict table (per mixed lane, per canceled WP)
| Canceled WP entered implementation? | Attribution | Canceled final content | Verdict |
|---|---|---|---|
| no | — | — | unchanged (today's behaviour) |
| yes | missing / open window / off-spine / contested / unreadable | — | REFUSE |
| yes | resolved | none unsuperseded (or canceled state = pre-state) | unchanged (PASS if nothing else diverges) |
| yes | resolved | target carries the canceled state and the window base did not | FAIL (`canceled_content`) |
| yes | resolved | target and window base both carry the canceled state, and the pre-state was produced by a surviving lane commit (approved work undone) | FAIL (`canceled_content`) |
| yes | resolved | target and window base both carry the canceled state, and the pre-state was inherited (not produced on the lane) | unchanged (target already had it) |
| yes | resolved | target is neither the canceled state, the pre-state, nor the window-base state | REFUSE (merged with an independent change) |

REFUSE precedes FAIL. Lanes that are not mixed are unaffected.

## C4 Messages
- FAIL: names path, canceled WP, lane; recovery: revert the WP's change on the lane through a surviving WP's governed work, re-run `spec-kitty consolidate`.
- REFUSE: names lane, WP, the missing/contradictory evidence; same recovery.
