# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · pi · WP01: measured before changing anything (cProfile + two interleaved A/B experiments). Root cause: 121 URN->stem lookups each created a fresh ResolutionPass (5028 _parse_id calls, 122 pass instances), plus one whole-catalog scan per activation. Fix: one shared ResolutionPass resolving the whole target batch before the first write - the seam #5526 gave the render loops. Deterministic effect: 5028 -> 240 parses; interleaved A/B 80.3->49.8 s and 95.2->66.4 s medians (absolute seconds never asserted).
