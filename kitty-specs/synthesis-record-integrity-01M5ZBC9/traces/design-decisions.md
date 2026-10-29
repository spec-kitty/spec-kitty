# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-27 · claude · Operator: run-wide lock per worktree in git common dir (event_log_append placement pattern), 10s wait then CHARTER_SYNTHESIS_LOCK_HELD; #6456 skip stripping non-regenerated artifacts (a stamped successor edge would make the artifact reach-only and change delivery).

2026-10-27 · claude · Post-spec squad (architect-alphonso, reviewer-renata): lock span moved to just after assert_charter_yaml_sound (convergence + fresh seed write earlier); #6443 dead-edge filter kept separate from the #6456 applies filter; restamp_bundle_hash takes the lock (operator); activation config + ledger migration residual filed #6719; injectable timeout; deterministic two-Event race; fallback lock under .kittify/runtime.

2026-10-27 · claude · Pre-merge squad (reviewer-renata, architect-alphonso): LAND both; converged MEDIUM: FR-011 restamp lock raised a false 'Nothing was written' error with a raw traceback in activate/presets/interview/migration. Operator (2026-10-27): restamp warns on stderr and skips when the lock is held or git unusable. Follow-ups: kernel anchored lock-path helper; replace the ... sentinel in legacy_applies_edges.
