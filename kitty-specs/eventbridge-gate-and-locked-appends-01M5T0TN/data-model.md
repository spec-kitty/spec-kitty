# Data model

## WorkPackageTransition (port input, frozen dataclass)

| Field | Type | Meaning |
|---|---|---|
| `write_location` | `Path` | the resolved Mission directory the unit lands in (ADR 2026-10-22-1 D-3) |
| `rows` | `tuple[TransitionRow, ...]` | one durability unit: the transition, then its annotation(s); never empty |
| `write_contract` | `object \| None` | the CLI's resolved write contract (`EventLogWriteContract` for the coordination door, `None` for the flat shell); opaque to the domain |

**Invariant:** the unit lands whole or not at all; rows keep their order.

## TransitionRow (Protocol)

`event_id: str`, `to_dict() -> dict[str, Any]`. `StatusEvent` and `InnerStateChanged` satisfy it.

## Ledger append unit (kernel)

One or more `str` lines, each without `\n`. They are joined with `\n` plus a final `\n` and encoded as UTF-8: one `os.write`, then `fsync`.

**Refusals (all subclass `OSError`):**
- `LedgerTornTailError` (`LEDGER_TORN_TAIL`)
- `LedgerLockTimeoutError` (`LEDGER_LOCK_TIMEOUT`)
- `LedgerShortWriteError` (`LEDGER_SHORT_WRITE`)

A precondition error is the caller's own exception type, raised before any byte is written.
