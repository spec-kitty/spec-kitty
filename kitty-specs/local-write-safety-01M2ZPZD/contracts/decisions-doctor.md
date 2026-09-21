# Contract: decisions-index reconciler (`spec-kitty doctor` subcommand)

**Surface**: `src/specify_cli/cli/commands/_decisions_doctor.py`, mirroring the
`_mission_state_doctor.py` *extraction shape* PR #4813 establishes (structure only).

## Canonical authority (corrected)
The reconciler rebuilds `decisions/index.json` from the **decision event log**, applying the
**decisions forward event→IndexEntry mapping** — NOT `status.reducer.reduce()` (that reduces a
different `spec_kitty_events` status-lane schema and cannot be reused here).

**Single fold, no second reducer.** Today the forward writer (`decisions/service.py`
`open_decision`/`_terminal_command`) builds the `IndexEntry` from CLI params and *derives* the
event from it (`emit_decision_opened(..., entry=entry)`). The reconciler needs the **inverse**
event→IndexEntry fold. To avoid a second source of truth for "what a decision event means":
- Factor **one canonical `event → IndexEntry` fold** and have the reconciler consume it (ideally
  the forward path is refactored to share the same mapping, so they cannot drift).
- The reconciler must not hand-roll an independent interpretation of the opened/resolved payloads.

## Command
`spec-kitty doctor decisions --mission <handle> [--json] [--repair]`
- **Diagnose (default)**: read-only; report entries in the log missing from the index (and index
  entries with no backing event).
- **`--repair`**: rebuild `index.json` from the log via the canonical fold, written atomically
  under the sidecar `index.json.lock`. No-op (exit 0, "clean", no write) when they already agree.

## Invariants
- I9 (index reconstructible from the log) must be **proven, not asserted**: a task asserts the
  `DecisionPointOpened` + resolved/terminal events **round-trip every `IndexEntry` field** the
  index needs (no field reconstructed wrong or dropped on `--repair`). If a field does not
  round-trip today, that is a prerequisite fix, surfaced before the reconciler is trusted.
- Repair never invents entries absent from the log, never drops log-backed entries.
- Runs under the same sidecar lock as the write path (I8) so a concurrent open/resolve cannot race.

## Acceptance
- Round-trip test: every IndexEntry field is recoverable from the opened+resolved events (proves I9).
- Seed a diverged corpus (log=8, index=5) → `--repair` yields index==log==8 (SC-002).
- Repair on an agreeing corpus is a no-op; `--json` output is stable/machine-readable.
