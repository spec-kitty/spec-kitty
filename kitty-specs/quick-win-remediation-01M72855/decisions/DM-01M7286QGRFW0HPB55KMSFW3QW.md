# Decision Moment `01M7286QGRFW0HPB55KMSFW3QW`

- **Mission:** `quick-win-remediation-01M72855`
- **Origin flow:** `specify`
- **Slot key:** `specify.status-log.writer-bytes`
- **Input key:** `writer_bytes`
- **Status:** `resolved`
- **Created:** `2026-11-10T08:11:46.072771+00:00`
- **Resolved:** `2026-11-10T08:11:47.378958+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

#7441: what must the status event-log writer guarantee about numbers and line endings?

## Options

- Refuse non-finite numbers (allow_nan=False, refusal as StoreError, nothing written) and write LF-only on every OS (newline="\n"); red test asserts the temp file newline
- Only NaN
- Other

## Final answer

Refuse non-finite numbers: serialisation uses allow_nan=False and a NaN/Infinity value refuses as StoreError naming the event, with nothing written. Write LF line endings on every OS by opening the temp file with newline set to LF; the red-first test asserts the newline argument of the temp-file open (CPython on Linux cannot observe CRLF), plus a portable byte pin with no CRLF. After the fix the serialised line equals the spec-kitty-events byte rule.

## Rationale

_(none)_

## Change log

- `2026-11-10T08:11:46.072771+00:00` - opened
- `2026-11-10T08:11:47.378958+00:00` - resolved (final_answer="Refuse non-finite numbers: serialisation uses allow_nan=False and a NaN/Infinity value refuses as StoreError naming the event, with nothing written. Write LF line endings on every OS by opening the temp file with newline set to LF; the red-first test asserts the newline argument of the temp-file open (CPython on Linux cannot observe CRLF), plus a portable byte pin with no CRLF. After the fix the serialised line equals the spec-kitty-events byte rule.")
