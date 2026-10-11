# Decision Moment `01M4PG2K9Q660VYNYGSCZ3DDXM`

- **Mission:** `retrospective-record-path-relative-01M4PG0M`
- **Origin flow:** `specify`
- **Slot key:** `specify.scope.migration`
- **Input key:** `backfill_historical_paths`
- **Status:** `resolved`
- **Created:** `2026-10-11T22:07:02.455979+00:00`
- **Resolved:** `2026-10-11T22:07:04.382128+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Should the fix also backfill/migrate absolute record_path values already committed to existing status.events.jsonl logs, or only make newly-emitted events repository-relative?

## Options

- forward-only
- forward-plus-backfill
- Other

## Final answer

forward-only: emit newly-written RetrospectiveCaptured events with a repository-relative record_path. No historical backfill. Rationale: issue #5868 asks only that the recorded path be repository-relative; the single existing leak was hand-scrubbed on #5856. A cross-repo backfill of already-committed append-only logs is a distinct, larger concern (append-only logs are immutable history) and is out of scope — notable as a possible follow-up only if a leak scan later finds more occurrences.

## Rationale

_(none)_

## Change log

- `2026-10-11T22:07:02.455979+00:00` — opened
- `2026-10-11T22:07:04.382128+00:00` — resolved (final_answer="forward-only: emit newly-written RetrospectiveCaptured events with a repository-relative record_path. No historical backfill. Rationale: issue #5868 asks only that the recorded path be repository-relative; the single existing leak was hand-scrubbed on #5856. A cross-repo backfill of already-committed append-only logs is a distinct, larger concern (append-only logs are immutable history) and is out of scope — notable as a possible follow-up only if a leak scan later finds more occurrences.")
