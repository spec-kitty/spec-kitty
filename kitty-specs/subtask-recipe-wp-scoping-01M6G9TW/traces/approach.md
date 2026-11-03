# Tracer: approach

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-03 · python-pedro · Scope split after grounding: the write-path half of #7108 (mark-status refusing to attribute an id two WPs own) was already fixed on main in 642359bbae (#6463). The residual defect is the printed advice — the move-task refusal, the implement prompt's WHEN DONE block and the three implement runbook sites all kept emitting the unscoped command, which the fixed mark-status then refuses. So this mission changes emitters only: one pure renderer, four call sites, no ownership logic touched.
