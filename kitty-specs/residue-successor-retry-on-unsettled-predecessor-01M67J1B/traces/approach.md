# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-10-30 · claude · Ground first: reproduced the pinned C-006 xfail under --runxfail on current main (successor missing from the selected set) before touching code; traced the record flow backfill plan -> adoption projection -> selection -> runner skip gate to find the one shared seam (reselect_when_recorded).
