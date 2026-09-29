# Decision Moment `01M3NSKBMEKR60XKRJSYQC41G3`

- **Mission:** `requirement-id-grammar-01M3NRCA`
- **Origin flow:** `specify`
- **Slot key:** `specify.gating.rejected-ref-verdicts`
- **Input key:** `rejected_ref_verdicts`
- **Status:** `resolved`
- **Created:** `2026-09-29T05:18:32.590640+00:00`
- **Resolved:** `2026-09-29T05:18:34.040081+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Once rejected refs are kept on disk, which rejection reasons fail finalize-tasks and runtime readiness?

## Options

- Malformed + unknown fail
- Only unknown FR/NFR/C fail
- Other

## Final answer

Malformed + unknown fail; foreign_qualified never fails; a rejected ref never un-maps the WP's valid refs

## Rationale

_(none)_

## Change log

- `2026-09-29T05:18:32.590640+00:00` — opened
- `2026-09-29T05:18:34.040081+00:00` — resolved (final_answer="Malformed + unknown fail; foreign_qualified never fails; a rejected ref never un-maps the WP's valid refs")
