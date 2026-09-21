---
affected_files: []
cycle_number: 2
mission_slug: local-write-safety-01M2ZPZD
reproduction_command:
reviewed_at: '2026-09-20T18:19:43Z'
reviewer_agent: claude
wp_id: WP03
---

# WP03 cycle-2 — fold in review follow-ups A + B (operator-directed)

WP03 was approved on substance. The operator directed that the two follow-ups the
reviewer flagged be **folded into WP03 now** (not deferred). Both fixes are within
WP03's owned surface (`src/specify_cli/cli/commands/_decisions_doctor.py`) — no
owned_files change, no re-finalize.

## Fold A — `doctor decisions --repair` must NOT silently mis-attribute a slot_key-origin decision
- **Defect**: the wire event only carries a single `step_id` field (upstream
  `spec_kitty_events.decisionpoint` schema — `emit.py:213` writes
  `entry.step_id or entry.slot_key` into it). So `fold_events` rebuilding a
  slot_key-origin decision reconstructs it as `step_id=<slot_key value>, slot_key=None`
  — silently different from the original.
- **Constraint**: the real schema fix (carry step_id AND slot_key + summary_json) is
  **upstream** in `spec_kitty_events` (a client-repo boundary — do NOT edit it here).
- **Required in-surface fold**: `--repair` (and `fold_events`) must **detect** an entry it
  cannot faithfully rebuild (a decision whose original had a distinct `slot_key`, i.e. the
  wire is lossy for it) and **warn loudly / refuse to rewrite that entry** rather than
  silently mis-attributing it. Membership-only healing (identity preserved: decision_id /
  input_key) is fine to keep; attribution it cannot prove must not be fabricated. Add a
  test asserting a slot_key-origin decision triggers the warn/refuse path (no silent
  `step_id=<slot_key>` rewrite). Reference the upstream schema gap in a code comment as the
  root cause + a `# Follow-up:` handle so it's tracked as a separate upstream item.

## Fold B — `_repair` must read the event log INSIDE the sidecar lock
- **Defect**: `_diagnose` captures the log snapshot pre-lock; `_repair` then acquires the
  lock and rebuilds from that **stale** snapshot. A concurrent open/resolve landing between
  the diagnose read and the lock acquisition is dropped by the repair (partially defeats I8).
- **Required fold**: in `_repair`, re-read the event log **inside** the `machine_file_lock`
  acquisition (do not rebuild from the pre-lock `_diagnose` snapshot). Add/extend a test
  proving a concurrent append during repair is not lost (or, minimally, that the rebuild
  reads under the lock).

## Keep everything else as-is
The approved substance (service-level lock across both critical sections, red-first
barrier-synchronized key-set concurrency proof, I9 full-object round-trip, one canonical
fold, doctor wiring) is correct — do not regress it. Re-run the full WP03 test set +
`ruff format --check` (WP04 was rejected for a format miss — keep this green).
