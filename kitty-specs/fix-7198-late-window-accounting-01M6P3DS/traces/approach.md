# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-05 · python-pedro · Extend the merged #7124 assertion in place (assert_late_window_landed) rather than adding a second late-window check: it is already called on both run kinds after the projection and before the approved-tip advance, so widening it preserves the ordering guarantee #7124 established.
