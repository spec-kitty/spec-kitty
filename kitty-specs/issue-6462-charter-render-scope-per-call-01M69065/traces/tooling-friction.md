# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-31 · python-pedro · Grounding friction: on this shared host (~20 concurrent agents in different clones) the global ~/.kittify/cache/agent-commands-freshness.lock stamp never matches, so startup assets re-render twice per call (~1.5 s). Isolated-HOME runs show the warm path is 0.01 s. Recorded as a shared-machine artefact (#6470 scope), not a product defect; absolute seconds are reported, never asserted.

2026-10-31 · python-pedro · The branch was rebased externally onto a newer main (new SHAs, committer Ivan Melck) at ~20:47; adopted the remote head. CI on 903fc91e: 36 checks pass, 'architectural battery 2/2' fails only at its post-test universe-prestep bookkeeping step (battery itself 2351 passed, 1 xfailed; the same collect->pytest->check sequence exits 0 locally), and the rest stay queued behind a stalled fleet. PR left in draft.
