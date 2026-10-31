# Decision Moment `01M68ZS6CPNG2HABNMAK7J142R`

- **Mission:** `activation-writes-under-synthesis-lock`
- **Origin flow:** `specify`
- **Step id:** `specify.success_criteria`
- **Input key:** `success_criteria`
- **Status:** `resolved`
- **Created:** `2026-10-31T12:43:33.142457+00:00`
- **Resolved:** `2026-10-31T12:45:38.194390+00:00`
- **Opened by:** `22272470+Ivan-Melck@users.noreply.github.com`
- **Other answer:** `false`

## Question

How will we know this Mission is successful?

## Options

_(none)_

## Final answer

A two-writer test proves each race is closed: (a) a charter deactivate that races a synthesis activation append stays deactivated and the append survives, instead of one writer failing with precondition_changed or dropping the other's write; (b) apply_ledger_migration's manifest stamp cannot drop synthesis manifest entries written concurrently. Both writers hold the existing run-wide synthesis lock for their whole read-modify-write, a held lock is a bounded wait then a coded CHARTER_SYNTHESIS_LOCK_HELD refusal with nothing written, and the existing synthesis-lock, activation and migration suites stay green (issue #6719).

## Rationale

_(none)_

## Change log

- `2026-10-31T12:43:33.142457+00:00` — opened
- `2026-10-31T12:45:38.194390+00:00` — resolved (final_answer="A two-writer test proves each race is closed: (a) a charter deactivate that races a synthesis activation append stays deactivated and the append survives, instead of one writer failing with precondition_changed or dropping the other's write; (b) apply_ledger_migration's manifest stamp cannot drop synthesis manifest entries written concurrently. Both writers hold the existing run-wide synthesis lock for their whole read-modify-write, a held lock is a bounded wait then a coded CHARTER_SYNTHESIS_LOCK_HELD refusal with nothing written, and the existing synthesis-lock, activation and migration suites stay green (issue #6719).")
