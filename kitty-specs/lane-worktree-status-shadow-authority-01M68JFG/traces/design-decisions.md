# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · python-pedro · Re-anchored the handed root in the one guarded read-side seam (resolve_handle_to_read_path) using the existing worktree-topology authority. Rejected: a newest-timestamp-wins rule (the event log is the mutable authority) and a lenient transition guard (it would weaken a real gate). Status stays owned by the resolved surface.
