# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-09-27 · claude-orchestrator · Seed: single_branch topology on the thread branch; checks stay outside the status lock (NFR-001); reuse MISSION_NOT_READY rather than a new orchestrator error code (C-002).

2026-09-27 · claude-orchestrator · Post-spec squad (architect-alphonso, reviewer-renata) folded: row ownership rule with definition-equality; locked pre-stamp verdict re-check (FR-010) closes the gate-to-stamp window; gate covers both unlocked writers incl. alias/attribute calls; post-consolidation seam routing deferred (no production caller); CONTRACT_VERSION 1.7.0.

2026-09-27 · python-pedro · WP02: fixed #4974 by splicing the FRESH acceptance matrix under WP01's locked_reread_splice_and_write seam instead of overwriting with accept's stale pre-lock snapshot; FR-010 pre-stamp guard re-reads the verdict fresh under the same per-mission lock via locked_acceptance_verdict_guard before stamping. Only a planning-artifact-only mission (no acceptance-matrix.json by design) may bypass the guard; every other missing-matrix-dir case fails closed with AcceptanceError. Half-by-half proof: reverting the splice alone and the fresh-verdict judgement alone each independently turn the SC-001 regression test red, confirming both halves of the fix are load-bearing.
