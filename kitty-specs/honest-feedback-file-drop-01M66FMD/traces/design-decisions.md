# Design decisions — honest-feedback-file-drop-01M66FMD

- **[2026-10-30][plan] Edge predicate reuses the canonical predicates.** "Recordable edge" = `is_review_rejection_edge(old, target) or target in _APPROVAL_LANES`; no second source of truth.
- **[2026-10-30][plan] The edge arm precedes the exists/is-file arms.** On a non-recordable edge the flag is useless regardless of the path's validity, so the edge message wins over "file not found".
- **[2026-10-30][plan] No new guard slot.** `arbiter_persist_signal`'s prefix slice includes `_guard_feedback_file`; a leading arm inside it is inert on approval lanes, so the OLD-timing signals are provably unchanged.
