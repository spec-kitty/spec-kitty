# Decision Moment `01M66YQ2ZWJ6KDAH59GTBB24YM`

- **Mission:** `bound-failed-staging-retention-01M66YPB`
- **Origin flow:** `specify`
- **Slot key:** `specify.retention.bound`
- **Input key:** `failed_staging_keep`
- **Status:** `resolved`
- **Created:** `2026-10-30T17:46:26.684954+00:00`
- **Resolved:** `2026-10-30T17:46:30.465388+00:00`
- **Opened by:** `python-pedro`
- **Other answer:** `false`

## Question

How many failed .staging/<run_id>.failed/ directories should be kept? The issue allows 'the most recent N' and requires the latest failure stay for diagnosis.

## Options

- 1 (latest only)
- 3 (latest + two prior)
- 5 (latest + four prior)

## Final answer

3 (latest + two prior)

## Rationale

_(none)_

## Change log

- `2026-10-30T17:46:26.684954+00:00` — opened
- `2026-10-30T17:46:30.465388+00:00` — resolved (final_answer="3 (latest + two prior)")
