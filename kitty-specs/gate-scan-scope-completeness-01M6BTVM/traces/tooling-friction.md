# Tracer: tooling-friction

One entry per finding: `YYYY-MM-DD · actor · <text>`.

---

2026-11-01 · python-pedro · The coord topology created a worktree for the mission while the spec is a PRIMARY-partition artifact checked at the primary checkout HEAD, so planning artifacts were authored on the primary (topic) branch and the coord branch fast-forwarded to it; issue-verdict/tracer writes still land on the coord branch and were merged into the topic branch.
