# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · python-pedro · Grounding friction: on this shared host (~20 concurrent agents in different clones) the global ~/.kittify/cache/agent-commands-freshness.lock stamp never matches, so startup assets re-render twice per call (~1.5 s). Isolated-HOME runs show the warm path is 0.01 s. Recorded as a shared-machine artefact (#6470 scope), not a product defect; absolute seconds are reported, never asserted.
