# Decision Moment `01M393S7EVNPY707FPWYDCPDGM`

- **Mission:** `terminus-integrity-followups-01M393QR`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.ws2-depth`
- **Input key:** `ws2_depth`
- **Status:** `resolved`
- **Created:** `2026-09-24T07:06:23.067113+00:00`
- **Resolved:** `2026-09-24T07:07:10.132813+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How deep on WS2 (resume): both strategy-honoring and lane-tip SHA-preservation, or strategy-only?

## Options

- Both (a)+(b) — close #4982 #4997 #4985 #4991
- (a)-only — close #4985 #4991, defer #4982 #4997

## Final answer

Both (a) honor persisted MergeState.strategy on resume AND (b) lane-tip SHA-preservation on resume-consolidation, closing all four of #4982 #4997 #4985 #4991.

## Rationale

_(none)_

## Change log

- `2026-09-24T07:06:23.067113+00:00` — opened
- `2026-09-24T07:07:10.132813+00:00` — resolved (final_answer="Both (a) honor persisted MergeState.strategy on resume AND (b) lane-tip SHA-preservation on resume-consolidation, closing all four of #4982 #4997 #4985 #4991.")
