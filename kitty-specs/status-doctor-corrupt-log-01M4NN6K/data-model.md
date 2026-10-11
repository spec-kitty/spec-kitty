# Existing Status Doctor Contract Facts

Audience: software-engineer. Updated: 2026-10-11.

This Mission changes diagnosis only, not product architecture or stored schemas. Authority: `src/specify_cli/status/models.py`, `store.py`, `doctor.py` and [spec.md](spec.md).

- Mission owns a status event log and optional derived snapshot.
- Canonical reader accepts supported lifecycle/status/annotation records, skipping blank physical rows under existing behavior. A malformed row/read failure is not empty history.
- Snapshot's existing work_packages view supplies health checks but cannot certify log readability.
- Existing Finding carries severity, category, optional wp_id, message and recommended_action. A corrupt-log finding has ERROR severity and diagnostic file/reason/location when truthful; exact category is a bounded implementation choice.
- Existing DoctorResult exposes findings, has_errors and is_healthy. Unreadable history necessarily has_errors=true and is_healthy=false.

## Invariants

1. No stored-file byte or missing-file-state change.
2. Reader remains the sole record acceptance authority.
3. Correct physical 1-based JSONL record location when available, never invented whole-file I/O location.
4. Invalid history is not converted to empty membership, and dependent checks cannot advise destructive repair.
5. No lifecycle transition, event envelope field or snapshot schema changes.

## Drift classification

Review against [reasons-canvas.md](reasons-canvas.md): approved scope, documented local deviation, stale canvas, or blocking scope/safeguard violation. A reader-location-only edit may be documented; decision-doctor, repair or general reducer edits block as scope drift.
