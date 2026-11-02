# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-02 · pi/deepseek-v4.1-flash · Grounding the target suite turned up a pre-existing red on the merge base: the approved reopen refuses --review-feedback-file with 'this edge writes no review cycle'. _feedback_edge_recordable (#6699, merged 2026-11-02T09:21Z) landed after the #6845 landing fix, so the FR-015 evidence arm is broken on main. #6699's test matrix never claims approved -> in_progress, so nothing pinned the loss.
