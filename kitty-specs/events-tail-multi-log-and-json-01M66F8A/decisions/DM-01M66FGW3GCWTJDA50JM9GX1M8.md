# Decision Moment `01M66FGW3GCWTJDA50JM9GX1M8`

- **Mission:** `events-tail-multi-log-and-json-01M66F8A`
- **Origin flow:** `specify`
- **Slot key:** `specify.json-flag.semantics`
- **Input key:** `json_flag_semantics`
- **Status:** `resolved`
- **Created:** `2026-10-30T13:20:54.384521+00:00`
- **Resolved:** `2026-10-30T13:21:02.114514+00:00`
- **Opened by:** `cli`
- **Other answer:** `false`

## Question

Should --json stay a JSON-only default (flag dropped as no-op) or flip to opt-in with a human-readable default output?

## Options

- human-readable default, --json opts into JSON lines (docs query precedent)
- drop the flag, JSON-only forever
- keep JSON default, add --human

## Final answer

Human-readable default; --json opts into JSON lines (the docs query --json precedent). The issue prefers implementing a human-readable mode so --json means something; pre-GA 4.0.0rc is the window to flip the default; --json output stays byte-identical for scripted consumers.

## Rationale

_(none)_

## Change log

- `2026-10-30T13:20:54.384521+00:00` — opened
- `2026-10-30T13:21:02.114514+00:00` — resolved (final_answer="Human-readable default; --json opts into JSON lines (the docs query --json precedent). The issue prefers implementing a human-readable mode so --json means something; pre-GA 4.0.0rc is the window to flip the default; --json output stays byte-identical for scripted consumers.")
