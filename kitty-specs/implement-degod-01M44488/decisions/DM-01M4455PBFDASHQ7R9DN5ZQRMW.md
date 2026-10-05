# Decision Moment `01M4455PBFDASHQ7R9DN5ZQRMW`

- **Mission:** `implement-degod-01M44488`
- **Origin flow:** `specify`
- **Slot key:** `specify.placement.c004-removal-shape`
- **Input key:** `c004_removal_shape`
- **Status:** `resolved`
- **Created:** `2026-10-04T19:10:09.775072+00:00`
- **Resolved:** `2026-10-04T19:10:17.766774+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How should #5232 remove the C-004 meta-derived fallback: (A) make placement_ref required and fail closed on any context-resolution error, or (B) resolve through the write-shaped placement seam and fail closed only when that seam cannot resolve?

## Options

- A: fail closed on any context-resolution error
- B: write-shaped placement seam, fail closed only when it cannot resolve
- Other

## Final answer

B: write-shaped placement seam, fail closed only when it cannot resolve. Resolved autonomously under the operator's semi-automatic brief (fold #5232 in, stop only on a real behaviour-change decision). Option B keeps the degrade owned by the placement seam, does not newly refuse flat missions or the unmaterialized window, and follows the mission_record_analysis precedent (#5113). Guard: a characterization test must show the write-shaped ref equals the read-shaped placement_ref wherever the latter resolves; if they diverge in a reachable case, escalate to the operator.

## Rationale

_(none)_

## Change log

- `2026-10-04T19:10:09.775072+00:00` — opened
- `2026-10-04T19:10:17.766774+00:00` — resolved (final_answer="B: write-shaped placement seam, fail closed only when it cannot resolve. Resolved autonomously under the operator's semi-automatic brief (fold #5232 in, stop only on a real behaviour-change decision). Option B keeps the degrade owned by the placement seam, does not newly refuse flat missions or the unmaterialized window, and follows the mission_record_analysis precedent (#5113). Guard: a characterization test must show the write-shaped ref equals the read-shaped placement_ref wherever the latter resolves; if they diverge in a reachable case, escalate to the operator.")
