# Decision Moment `01M2VZTDWRMQH5WY1FKV6WR2S3`

- **Mission:** `corrupt-state-file-guards-01M2VZS0`
- **Origin flow:** `specify`
- **Slot key:** `specify.error_presentation.consistency`
- **Input key:** `error_presentation_shape`
- **Status:** `resolved`
- **Created:** `2026-09-19T04:47:00.504443+00:00`
- **Resolved:** `2026-09-19T04:49:12.344370+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Should the new decisions/index.json error carry the same 'run: spec-kitty doctor' remediation hint that the meta.json (MissionMetaReadError) path emits, so both corrupt-state errors read identically to operators?

## Options

- Yes — unify on the doctor-hint shape for both
- No — keep decisions structured {code,error,details} only, meta keeps its message
- Other

## Final answer

Yes — unify on the doctor-hint shape for both; both corrupt-state errors read identically to operators (structured payload MAY carry code/details but MUST include the fail-closed + run: spec-kitty doctor guidance)

## Rationale

_(none)_

## Change log

- `2026-09-19T04:47:00.504443+00:00` — opened
- `2026-09-19T04:49:12.344370+00:00` — resolved (final_answer="Yes — unify on the doctor-hint shape for both; both corrupt-state errors read identically to operators (structured payload MAY carry code/details but MUST include the fail-closed + run: spec-kitty doctor guidance)")
