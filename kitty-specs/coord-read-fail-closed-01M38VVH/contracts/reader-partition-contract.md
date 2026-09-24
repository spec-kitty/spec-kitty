# Contract — reader resolves the authoritative partition (Findings A & B)

## Tracer-append (Finding A / #4959) — `retrospective/tracer_writer.py`

Guarantees:
1. `_read_current_coord_content` fails closed (propagates the seam raise) when the coord surface is unresolved/unmaterialised — never returns `""` that the writer turns into a `_default_header` clobber.
2. An `UnicodeDecodeError` on an *existing* traces file → **refuse**, not `""` (corruption is not "no content").
3. A genuinely-absent file on a *resolved* coord surface still yields empty (legitimate first append) — no regression for the normal path.

Acceptance (red-first):
- **AC-T1**: from an unmaterialised-coord checkout, `agent tracer-append` on a populated `traces/<cat>.md` leaves the file byte-intact and fails closed (0 findings lost). Pre-fix: file clobbered to header+entry.
- **AC-T2**: undecodable byte → refuse, file untouched.
- **AC-T3**: materialised, present file → appends normally.

## Decision ledger (Finding B / #4966) — `decisions/service.py`

Guarantees:
1. `_resolve_mission_id` / `_mission_dir` resolve `meta.json` via **`PRIMARY_METADATA`** (never `STATUS_STATE`/coord), so a materialised status-only husk no longer yields `MISSION_NOT_FOUND`.
2. The decision service and `acceptance/__init__.py::_has_blocking_clarification_marker` read the ledger from the **same PRIMARY partition** — no split-brain; a deferred decision reaches the index `accept` reads; `accept` is not permanently blocked.
3. The `decisions/service.py:157-167` docstring is corrected (a materialised coord worktree does **not** carry `meta.json`).

Acceptance (red-first):
- **AC-D1**: on a coord mission with a materialised husk, `agent decision open` resolves (no `MISSION_NOT_FOUND`). Pre-fix: `MISSION_NOT_FOUND`.
- **AC-D2**: a deferred→resolved decision lets `accept` proceed (no permanent block); `verify` reflects the same state. Pre-fix: permanent block, no CLI way out.
- **AC-D3**: non-coord / flat missions' decision flows unchanged (regression).
