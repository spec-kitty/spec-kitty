# Tracer: design-decisions

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-05 · pi:deepseek-v4.1-flash-1017:python-pedro:implementer · Pin the full local-fact sentence `the lane branch kitty/mission-fx-lane-b does not exist in this checkout` in the existing Git-backed test rather than a substring. A looser `does not exist` assertion would not distinguish this sibling-path sentence from the never-created shape, and a second test file would create a second wording owner. The existing lane-tip, `If it did exist`, and never-created-negative assertions stay, so one fixture still discriminates all three shapes.
