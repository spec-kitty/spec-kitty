# Decision Moment `01M7286MYPH1ASNXT7K7ZSKWSB`

- **Mission:** `quick-win-remediation-01M72855`
- **Origin flow:** `specify`
- **Slot key:** `specify.status-log.line-framing`
- **Input key:** `line_framing`
- **Status:** `resolved`
- **Created:** `2026-11-10T08:11:43.447006+00:00`
- **Resolved:** `2026-11-10T08:11:44.784428+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

#7439: how should the status event-log readers frame rows and report JSON-limit failures?

## Options

- One shared line splitter (LF, CRLF, lone CR only) plus one decode helper mapping ValueError/RecursionError to StoreError across the store.py readers
- Per-site patches
- Other

## Final answer

One shared line splitter in status/store.py that ends a row only at LF, CRLF or a lone CR, used by every store.py text reader (seed_scratch_event_log, the strict text readers, read_events_lenient); and one decode helper that maps ValueError (incl. the 4300-digit integer limit) and RecursionError (deep nesting) to StoreError for the strict readers, a skipped row for the lenient reader, and ValueError for seed_scratch_event_log (its documented type). Splitters outside store.py are a follow-up issue.

## Rationale

_(none)_

## Change log

- `2026-11-10T08:11:43.447006+00:00` - opened
- `2026-11-10T08:11:44.784428+00:00` - resolved (final_answer="One shared line splitter in status/store.py that ends a row only at LF, CRLF or a lone CR, used by every store.py text reader (seed_scratch_event_log, the strict text readers, read_events_lenient); and one decode helper that maps ValueError (incl. the 4300-digit integer limit) and RecursionError (deep nesting) to StoreError for the strict readers, a skipped row for the lenient reader, and ValueError for seed_scratch_event_log (its documented type). Splitters outside store.py are a follow-up issue.")
