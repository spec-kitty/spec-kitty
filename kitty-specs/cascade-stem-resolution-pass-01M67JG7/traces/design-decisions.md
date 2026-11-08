# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · pi · Kept scope to the redundancy that has an existing blessed seam (ResolutionPass). The remaining per-target catalog scan (list_available_detailed, 114 scans for 6 kinds) needs a batch activation seam on ActiveCharterManager and changes per-target deny/warning semantics: deferred to a follow-up issue rather than folded in, per locality-of-change and the operator's 'tight mission' rule.
