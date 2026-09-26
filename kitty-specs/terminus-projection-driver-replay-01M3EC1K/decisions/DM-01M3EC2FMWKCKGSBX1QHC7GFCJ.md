# Decision Moment `01M3EC2FMWKCKGSBX1QHC7GFCJ`

- **Mission:** `terminus-projection-driver-replay-01M3EC1K`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.fix-approach`
- **Input key:** `fix_approach`
- **Status:** `resolved`
- **Created:** `2026-09-26T08:07:27.132501+00:00`
- **Resolved:** `2026-09-26T08:08:34.266713+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

How should #5038 be remediated given Phase R proved P1/P2 are byte-identical lossless union-driver outputs with no discriminator, and #5021-r2 is soundly unfixable?

## Options

- Option B: driver-replay attribution for the projection proof (flips P1 to PASS soundly) + re-ground test_5038_p2 onto genuine coord-content loss; keep #5021-r2 honest xfail
- Option A: keep both as honest xfails, no code
- Escalate to charter/ADR first

## Final answer

Option B: replace the projection proof coord==target byte-check with driver-replay attribution (landed blob == deterministic merge driver output from checkpoint/pre-merge-target/coord), flipping test_5038_p1 RED->green soundly; re-ground test_5038_p2 onto a genuinely-lossy scenario so the fail-closed floor still bites; keep #5021-r2 (attribution-axis, src/shared.py stock-git manual resolution) as an honest strict-xfail and split it to its own tracked issue. Operator-confirmed floor re-adjudication.

## Rationale

_(none)_

## Change log

- `2026-09-26T08:07:27.132501+00:00` — opened
- `2026-09-26T08:08:34.266713+00:00` — resolved (final_answer="Option B: replace the projection proof coord==target byte-check with driver-replay attribution (landed blob == deterministic merge driver output from checkpoint/pre-merge-target/coord), flipping test_5038_p1 RED->green soundly; re-ground test_5038_p2 onto a genuinely-lossy scenario so the fail-closed floor still bites; keep #5021-r2 (attribution-axis, src/shared.py stock-git manual resolution) as an honest strict-xfail and split it to its own tracked issue. Operator-confirmed floor re-adjudication.")
